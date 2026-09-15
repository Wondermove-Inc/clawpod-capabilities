"""Offline installer selection and guidance for the standalone ClawPod Node app."""
from __future__ import annotations

import ipaddress
import json
import re
from pathlib import Path
from urllib.parse import unquote_to_bytes, urlsplit

REPOSITORY = "https://github.com/Wondermove-Inc/clawpod-capabilities"
TARGETS = {
    ("linux", "x64"): ("linux-x64", "deb"),
    ("macos", "arm64"): ("darwin-arm64", "pkg"),
    ("macos", "x64"): ("darwin-x64", "pkg"),
    ("windows", "x64"): ("win32-x64", "exe"),
}


def release_manifest() -> dict:
    """Read the package-local copy: registry installs need no sibling node tree."""
    value = json.loads(Path(__file__).with_name("installer-manifest.json").read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schemaVersion") != 1:
        raise ValueError("unsupported installer manifest")
    version = value.get("version")
    if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("invalid installer version")
    tag = f"node-v{version}"
    if value.get("releaseTag") != tag or value.get("releaseUrl") != f"{REPOSITORY}/releases/tag/{tag}":
        raise ValueError("invalid installer release")
    if "installerSourceCommit" in value and (
        not isinstance(value["installerSourceCommit"], str)
        or not re.fullmatch(r"[a-f0-9]{40}", value["installerSourceCommit"])
    ):
        raise ValueError("invalid installer source commit")
    for key in ("runtimeVersion", "nodeVersion"):
        if not isinstance(value.get(key), str) or not re.fullmatch(r"\d+\.\d+\.\d+", value[key]):
            raise ValueError("invalid runtime version")
    if value.get("channel") not in {"preview", "stable"} or not isinstance(value.get("signed"), bool):
        raise ValueError("invalid release metadata")
    validation = value.get("validation")
    if not isinstance(validation, dict) or any(validation.get(key) not in {"passed", "not-run", "failed"} for key in ("linuxOfflineInstall", "nativeMacOS", "nativeWindows", "desktopLoginStartup")):
        raise ValueError("invalid validation metadata")
    artifacts = value.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != len(TARGETS):
        raise ValueError("invalid installer artifacts")
    seen = set()
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            raise ValueError("invalid installer artifact")
        target = (artifact.get("platform"), artifact.get("arch"))
        if target not in TARGETS or target in seen:
            raise ValueError("unsupported or duplicate installer target")
        seen.add(target)
        suffix, extension = TARGETS[target]
        filename = f"ClawPod-Node-{version}-{suffix}.{extension}"
        if artifact.get("filename") != filename or artifact.get("url") != f"{REPOSITORY}/releases/download/{tag}/{filename}":
            raise ValueError("invalid installer download URL")
        if not isinstance(artifact.get("sha256"), str) or not re.fullmatch(r"[a-f0-9]{64}", artifact["sha256"]):
            raise ValueError("invalid installer checksum")
        if type(artifact.get("bytes")) is not int or artifact["bytes"] <= 0:
            raise ValueError("invalid installer size")
    return value


def ipv4_number(part: str) -> int:
    """Parse a WHATWG IPv4 component, including legacy hexadecimal and octal."""
    if not part:
        raise ValueError("empty IPv4 component")
    radix = 10
    if part.lower().startswith("0x"):
        radix, part = 16, part[2:]
    elif len(part) > 1 and part.startswith("0"):
        radix, part = 8, part[1:]
    if not part:
        return 0
    digits = {10: r"[0-9]+", 8: r"[0-7]+", 16: r"[0-9a-fA-F]+"}
    if not re.fullmatch(digits[radix], part):
        raise ValueError("invalid IPv4 component")
    return int(part, radix)


def normalized_host(host: str) -> str:
    if ":" in host:
        if "%" in host:
            raise ValueError("IPv6 zone identifiers are not supported")
        return str(ipaddress.IPv6Address(host))
    host = unquote_to_bytes(host).decode("utf-8").lower()
    # Leave Unicode domain conversion to the app's WHATWG parser. Python's
    # IDNA2003 codec can silently retarget names (straße -> strasse).
    # WHATWG domain parsing allows underscores and does not enforce DNS label
    # lengths/hyphen placement. Reject URL delimiters, not valid app hostnames.
    if not host or re.search(r"[\x00-\x20\x7f#%/:<>?@\[\\\]\^|]", host):
        raise ValueError("invalid hostname")
    parts = host.split(".")
    if len(parts) > 1 and parts[-1] == "":
        parts.pop()
    try:
        ipv4_number(parts[-1])
        numeric = True
    except ValueError:
        numeric = re.fullmatch(r"[0-9]+", parts[-1]) is not None
    if not numeric:
        return host
    # A domain ending in a number must parse entirely as IPv4. The last
    # component fills the remaining bytes (127.1 and 2130706433 are loopback).
    if len(parts) > 4:
        raise ValueError("too many IPv4 components")
    numbers = [ipv4_number(part) for part in parts]
    if any(number > 255 for number in numbers[:-1]) or numbers[-1] >= 256 ** (5 - len(numbers)):
        raise ValueError("IPv4 component out of range")
    value = numbers[-1] + sum(number * 256 ** (3 - index) for index, number in enumerate(numbers[:-1]))
    return str(ipaddress.IPv4Address(value))


def gateway_address(raw: str) -> dict:
    """Match the app's root-URL and private-WS transport contract, without secrets."""
    raw = raw.strip()
    message = "Use a ws:// or wss:// Gateway root URL with a valid host and port, without credentials, path, query, or fragment."
    if not re.fullmatch(r"wss?://[^/?#\s\\]+/?", raw, re.IGNORECASE):
        raise ValueError(message)
    try:
        parsed = urlsplit(raw)
        host = parsed.hostname
        port = parsed.port
        if not host or "@" in parsed.netloc or port == 0:
            raise ValueError(message)
        host = normalized_host(host)
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
    except (ValueError, UnicodeError):
        raise ValueError(message) from None
    private = host == "localhost" or host.endswith((".localhost", ".local"))
    if address is not None:
        if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
            address = address.ipv4_mapped
        networks = ("127.0.0.0/8", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "100.64.0.0/10", "169.254.0.0/16", "::1/128", "fc00::/7", "fe80::/10")
        private = any(address in ipaddress.ip_network(network) for network in networks)
    if parsed.scheme == "ws" and not private:
        raise ValueError("Use ws:// for private or Tailscale IPs, localhost, .localhost, or .local names; use wss:// for other hosts.")
    authority = f"[{host}]" if ":" in host else host
    if port is not None and port != (443 if parsed.scheme == "wss" else 80):
        authority += f":{port}"
    # Keep the response field for existing consumers; Node 0.1.1 needs no opt-in.
    return {"url": f"{parsed.scheme}://{authority}", "privateWsOptInRequired": False}


def guidance(platform: str, filename: str) -> dict:
    install = {
        "linux": f"On a Debian/Ubuntu x64 desktop, open the DEB in the package installer or run sudo dpkg -i {filename}.",
        "macos": "Open the PKG and complete the installer, then open ClawPod Node from Applications.",
        "windows": "Run the EXE as your normal user, then open ClawPod Node from the Start menu.",
    }
    removal = {
        "linux": "Remove the package with sudo dpkg -r clawpod-node.",
        "macos": "Run /Applications/ClawPod Node.app/Contents/Resources/Uninstall ClawPod Node.command before moving the app to Trash. Each configured account on a shared Mac must run this command first.",
        "windows": "Uninstall ClawPod Node from Windows Installed apps.",
    }
    desktop = {
        "macos": "In Desktop setup, allow ClawPod Node in Screen & System Audio Recording and Accessibility (Device Control & Data Access on macOS 27). Use Open settings and Check again if needed. An ad-hoc app update may require removing the stale permission entry and adding the current app from Applications. Screen capture only; audio is not collected.",
        "windows": "Check Desktop setup in your logged-in, unlocked desktop. No macOS-style permission switch is needed; UAC/secure desktops and elevated applications may reject ordinary input.",
        "linux": "Check Desktop setup in a graphical session (glibc 2.36 or newer). X11 needs a reachable display and XTest. Wayland needs RemoteDesktop/ScreenCast portals and user screen/input sharing consent when control starts.",
    }
    return {
        "preparation": [
            "Step 1: run agent.status; if NeedsLogin, run agent.login, send the link to the user, and recheck Running. Keep an existing connection.",
            "Step 2: help the user install Tailscale from https://tailscale.com/download and sign in to the same tailnet on their computer; verify communication.",
            "Steps 3–4: confirm the computer OS/CPU and use installer.info to select its matching Node app. Metadata lookup does not perform sign-in.",
        ],
        "setup": [
            "Download the selected installer from its release and compare its SHA-256 with the manifest before opening it. Remote availability has not been checked.",
            "Give the requesting user the Gateway host's verified Tailscale IP, complete reachable WebSocket root URL, and a display name. Use ws://IP:PORT for a plain WebSocket listener; use wss:// only for a TLS endpoint. Tailscale sign-in does not add TLS. Confirm the actual listener/proxy port; do not infer it from a dashboard URL.",
            "Read the active Gateway authentication source with available authorized tools and give the requesting user the actual Gateway token separately from the URL. config.get and openclaw config get redact secrets; a masked value or SecretRef is not a usable token. If password mode is active, provide the corresponding password instead. Explain which local authentication field to paste it into.",
            install[platform],
            desktop[platform] + " Desktop components are inside ClawPod Node; no separate helper installation is needed. Missing GUI permission does not block Gateway connection setup.",
            "Open ClawPod Node. Its setup page opens in your default browser. Enter the supplied URL, display name, and credential in their separate fields.",
            "Save settings and select Start node. Private and Tailscale IP ws:// connections are always enabled; there is no checkbox to turn on.",
            "Approve the matching new device in the Agent Control UI using its device/request identity, then confirm the connection there. Existing pairing and command approval rules apply.",
            "Identify the connected Node ID with nodes action=status and inspect its capabilities. For GUI work use remote_computer with node: status, acquire, input with the returned frameId as frame_id, then release. Use exec host=node with node for CLI; a running sessionId is used with process for status, logs, input, or cancellation. Managed CLI needs Node 0.2.1 and the updated controlling Agent; no SSH server is needed. Use browser target=node with node for a compatible installed browser. Local computer remains the pod desktop. The Gateway Agent must also provide remote_computer.",
        ],
        "operations": {
            "start": "Select Start node in the ClawPod Node setup page.",
            "restart": "Select Reconnect to restart the node with saved settings.",
            "stop": "Select Stop. The node stays stopped when the app is reopened or you sign in again, until Start node is selected.",
            "startup": "Start when I sign in registers startup for the current user and their logged-in desktop session.",
            "status": "Running reports the local process only. Check the Agent Control UI for authenticated, paired, connected status; inspect timestamped failures in the app.",
            "close": "Closing the setup browser tab leaves the node running. Reopening ClawPod Node reuses its setup server.",
            "upgrade": "Install the newer matching package. Upgrades preserve settings and identity and attempt to resume previously active users.",
            "uninstall": removal[platform] + " User settings and device identity remain for reinstall; remove the separate .clawpod-node directory only when you intend to discard them.",
        },
        "stateDirectory": "%USERPROFILE%\\.clawpod-node" if platform == "windows" else "~/.clawpod-node",
        "stateCompatibility": "The app has its own state and startup service. Existing ~/.openclaw state is preserved. Use the app controls and OS package removal for this installation.",
        "network": "Complete agent and computer Tailscale sign-in and verify communication before connecting the Node app. Private and Tailscale IP ws:// connections need no opt-in. Use the Tailscale IP for a plain WebSocket listener. Localhost, .localhost, and .local names also support ws://; other hostnames, including .ts.net DNS names, require a real wss:// endpoint. Match the actual listener/proxy scheme and port.",
    }


def installer_info(args) -> tuple[dict, int]:
    out = {"ok": True, "command": "installer.info", "safetyClass": "S0", "status": "success", "effects": [], "errors": [], "redactions": ["credential"]}

    def fail(code, message, exit_code=2):
        return {**out, "ok": False, "status": "failed", "errors": [{"code": code, "message": message}]}, exit_code

    if not args.json or args.target != "local":
        return fail("INVALID_INPUT", "--json is required and --target must be local.")
    if not args.platform_name or not args.arch:
        return fail("INSTALLER_TARGET_REQUIRED", "Specify the computer's --platform linux|macos|windows and --arch x64|arm64.")
    target = (args.platform_name, args.arch)
    if target not in TARGETS:
        return fail("INSTALLER_TARGET_UNSUPPORTED", "Available installers are Linux x64, macOS arm64/x64, and Windows x64.")
    try:
        gateway = gateway_address(args.gateway_url) if args.gateway_url is not None else None
    except ValueError as exc:
        return fail("INVALID_GATEWAY_URL", str(exc))
    try:
        manifest = release_manifest()
    except (OSError, ValueError, TypeError):
        return fail("INSTALLER_MANIFEST_INVALID", "The bundled installer manifest is missing or invalid. Reinstall this harness package.", 6)
    artifact = next(item for item in manifest["artifacts"] if (item["platform"], item["arch"]) == target)
    out["installer"] = {key: manifest[key] for key in ("version", "runtimeVersion", "nodeVersion", "releaseTag", "releaseUrl", "channel", "signed")}
    out["installer"].update({key: artifact[key] for key in ("platform", "arch", "filename", "url", "sha256", "bytes")})
    out["installer"].update({"manifestSource": "bundled", "remoteAvailability": "unchecked"})
    out["installer"]["validation"] = {key: manifest["validation"][key] for key in ("linuxOfflineInstall", "nativeMacOS", "nativeWindows")}
    # Keep public test metadata outside the legacy login-identity redaction keyspace.
    out["installer"]["validation"]["desktopStartup"] = manifest["validation"]["desktopLoginStartup"]
    out["gateway"] = gateway
    out["guidance"] = guidance(args.platform_name, artifact["filename"])
    out["nextAction"] = {"kind": "handoff", "message": "Give the user the matching installer link, verified Gateway Tailscale address, complete connection URL, and actual Gateway token (or active password) in separate fields, followed by app setup steps. Use available tools to obtain connection values; this offline command does not read them. Confirm release availability before describing the download as available.", "resumeCommand": None}
    return out, 0
