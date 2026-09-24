"""Command security patterns — dangerous command detection for bash tool.

These patterns are used by the ``_bash`` handler in core.tools to scan
incoming shell commands before execution.
"""
import re

# Patterns that are ALWAYS blocked — these are definitively dangerous.
_DANGEROUS_PATTERNS: list[tuple[str, str]] = [
    # (regex pattern, description of risk)

    # ── Destructive file operations ────
    (r'\brm\s+-rf\b', "recursive force delete (rm -rf)"),
    (r'\bRemove-Item\s+-Recurse\s+-Force\b', "recursive force delete"),
    (r'\bdel\s+/[fq]\s', "force delete system files"),
    (r'\brm\s+.*/\s*(-rf)?\s*(--no-preserve-root)?\b', "dangerous recursive delete"),
    (r'\bmv\s+.*\s+/dev/null\b', "move file to null device"),

    # ── Disk / filesystem ────
    (r'>\s*/dev/sd[a-z]', "raw disk write"),
    (r'\bdd\s+if=', "raw disk copy (dd)"),
    (r'\bmkfs\.\w+\b', "filesystem format"),
    (r'\bFormat-Volume\b', "PowerShell volume format"),
    (r'\bmkswap\b', "swap partition format"),
    (r'\bfdisk\s+/dev/sd\b', "disk partition modification"),

    # ── Git safety ────
    (r'\bgit\s+push\s+--force\b', "force push to remote"),
    (r'\bgit\s+reset\s+--hard\b', "hard git reset"),

    # ── Permissions / system integrity ────
    (r'\bchmod\s+777\b', "world-writable permissions"),
    (r'\bchown\s+\d+\s+/\s', "change root ownership"),
    (r'\bicacls\s+.*\/grant\s+Everyone', "grant Everyone permissions"),
    (r'\bSet-ExecutionPolicy\b', "change execution policy"),

    # ── System control ────
    (r'\bRestart-Computer\b', "system restart"),
    (r'\bStop-Computer\b', "system shutdown"),
    (r'\bshutdown\s+[-/]', "system shutdown/restart"),
    (r'\breboot\b', "system reboot"),
    (r'\bpoweroff\b', "system poweroff"),
    (r'\bStop-Process\s+-Name\s+(winlogon|lsass|csrss|smss|services)', "critical process kill"),
    (r'\bsc\s+stop\b', "stop Windows service"),
    (r'\bRemove-Item\s+.*\\Windows\\', "delete Windows system files"),
    (r'\bkill\s+-9\s+1\b', "kill init/PID 1"),

    # ── Remote code execution ────
    (r'\bwget\b.*\|\s*(sh|bash|pwsh)', "pipe download to shell"),
    (r'\bcurl\b.*\|\s*(sh|bash|pwsh)', "pipe download to shell"),
    (r'\bInvoke-Expression\b.*(wget|curl|iwr)', "eval remote content"),
    (r'\bInvoke-WebRequest\b.*\|.*\bInvoke-Expression\b', "download & execute PowerShell"),

    # ── Data exfiltration ────
    (r'\b(nc|ncat|netcat)\s+.*-e\s+', "netcat reverse shell"),
    (r'\bbash\s+-i\s+>&\s+/dev/tcp/', "bash reverse shell"),
    (r'\bpython\s+-c\s+.*socket.*connect\b', "Python reverse shell"),
    (r'\b(whoami|id)\s.*\|.*(curl|wget)\b', "user info exfiltration"),

    # ── Container escape / privilege ────
    (r'\b(docker|podman)\s+run\s+--privileged\b', "privileged container run"),
    (r'\b(docker|podman)\s+exec\s+-it\s+.*\s+--pid=host\b', "container PID namespace escape"),
    (r'\bnsenter\s+--target\s+1\b', "namespace escape to init namespace"),

    # ── Network tampering ────
    (r'\biptables\s+-F\b', "flush iptables rules"),
    (r'\broute\s+add\s+-net\s+0\.0\.0\.0\b', "route table manipulation"),
    (r'\btcpkill\b', "kill TCP connections"),

    # ── Bypass coverage: separate flags, long options, symbolic notation ────
    (r'\brm\s+(-\w+\s+)*--?r(?:ecursive)?\b', "recursive delete (any flag form)"),
    (r'\bgit\s+push\s+(-f|--force)\b', "force push (short or long flag)"),
    (r'\bgit\s+push\s+.*--force-with-lease\b', "force push with lease"),
    (r'\bchmod\s+\d*7\d*7\d*7\b', "world-writable (any octal variant)"),
    (r'\bchmod\s+.*[ugo]\+[rwx]', "permissive symbolic chmod"),
    (r'\bcurl\b.*\$\(', "curl with command substitution"),
    (r'\bwget\b.*\$\(', "wget with command substitution"),
    (r'\bbash\s+-c\s*".*\$\(.*curl', "bash -c with curl substitution"),
    (r'\bbash\s+-c\s*\'.*\$\(.*curl', "bash -c with curl substitution (single quotes)"),
    (r'\btee\s+/dev/[hs]d[a-z]\b', "tee to raw device"),
    (r'\bdd\s+of=', "dd output to device (of= variant)"),
    (r'\bRemove-Item\s+.*-Recurse\b', "PowerShell recursive delete (any order)"),
    (r'\bmv\s+.*\s+/etc/', "move to /etc/"),
    (r'\bchown\s+-R\b', "recursive ownership change"),
]

# Patterns that are suspicious but not definitively malicious.
# These trigger a WARNING rather than a BLOCK.
_WARN_PATTERNS: list[tuple[str, str]] = [
    (r'\bdocker\s+(run|exec)\b', "docker container execution — verify image source"),
    (r'\bsudo\b', "superuser privileges requested"),
    (r'\bpip\s+install\b', "package installation — verify package name"),
    (r'\bnpm\s+install\s+-g\b', "global npm install — verify package name"),
    (r'\bchmod\s+\+x\b', "making file executable"),
    (r'\bsystemctl\s+(start|stop|restart|enable|disable)\b', "systemd service control"),
    (r'\bsource\s+.*\|\s*\b', "sourcing piped content"),
    (r'\beval\b', "eval usage — high risk of code injection"),
]


def scan_dangerous(command: str) -> tuple[list[str], list[str]]:
    """Scan a command for dangerous and suspicious patterns.

    Args:
        command: The shell command string to scan.

    Returns:
        A tuple of (blocked_risks, warning_risks) — each is a list of
        human-readable descriptions of the matched patterns.
    """
    blocked = []
    for pattern, risk_desc in _DANGEROUS_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            blocked.append(risk_desc)
    warnings = []
    for pattern, risk_desc in _WARN_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            warnings.append(risk_desc)
    return blocked, warnings
