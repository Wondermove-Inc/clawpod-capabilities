"""Standard exit codes for desktop skill."""

EXIT_SUCCESS = 0
EXIT_NOT_FOUND = 1
EXIT_TIMEOUT = 2
EXIT_APP_FAIL = 3
EXIT_ATSPI_FAIL = 4

# Allowed desktop sub-commands (whitelist for macro validation)
ALLOWED_COMMANDS = {
    'tree', 'find', 'click', 'dblclick', 'rclick', 'type', 'key',
    'select', 'focus', 'scroll', 'open', 'close', 'apps', 'active',
    'screenshot', 'chain', 'wait', 'read', 'table', 'macro',
    'selftest', 'snapshot',
}
