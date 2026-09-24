#!/usr/bin/env node

/**
 * WIDDX Nexus — Node.js wrapper for Python CLI & TUI
 * 
 * This script detects Python 3.10+, ensures a PEP 668 compliant virtual 
 * environment exists (at ~/.widdx/venv), installs Python dependencies,
 * and executes the correct Python entry point.
 */

import { spawn, spawnSync } from 'child_process';
import { fileURLToPath } from 'url';
import path from 'path';
import fs from 'fs';
import os from 'os';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Root of the project (one level up from bin/)
const projectRoot = path.resolve(__dirname, '..');

// Standard location of virtual environment (default: ~/.widdx/venv)
const defaultVenvPath = path.join(os.homedir(), '.widdx', 'venv');
const venvPath = process.env.WIDDX_VENV || defaultVenvPath;

// Find a suitable python command on the system
function getPythonCommand() {
    const commands = ['python3', 'python'];
    for (const cmd of commands) {
        try {
            const result = spawnSync(cmd, ['-c', 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")'], { encoding: 'utf8' });
            if (result.status === 0) {
                const [major, minor] = result.stdout.trim().split('.').map(Number);
                if (major >= 3 && minor >= 10) {
                    return cmd;
                }
            }
        } catch (e) {
            // Ignore and try the next command
        }
    }
    return null;
}

async function main() {
    const pythonCmd = getPythonCommand();
    if (!pythonCmd) {
        console.error('\x1b[31mError: Python >= 3.10 is required but was not found on your system.\x1b[0m');
        console.error('Please install Python 3.10 or higher and try again.');
        process.exit(1);
    }

    const pythonExe = process.platform === 'win32' 
        ? path.join(venvPath, 'Scripts', 'python.exe')
        : path.join(venvPath, 'bin', 'python');

    // If virtual environment does not exist, initialize it
    if (!fs.existsSync(pythonExe)) {
        console.log('\x1b[36m⊙ Initializing WIDDX Python Virtual Environment...\x1b[0m');
        console.log(`Creating virtual environment at: ${venvPath}`);
        
        // Ensure parent directory exists
        fs.mkdirSync(path.dirname(venvPath), { recursive: true });

        const createVenv = spawnSync(pythonCmd, ['-m', 'venv', venvPath], { stdio: 'inherit' });
        if (createVenv.status !== 0) {
            console.error('\x1b[31m✗ Failed to create python virtual environment.\x1b[0m');
            process.exit(1);
        }

        console.log('\x1b[36m⊙ Upgrading pip...\x1b[0m');
        spawnSync(pythonExe, ['-m', 'pip', 'install', '--quiet', '--upgrade', 'pip'], { stdio: 'inherit' });

        console.log('\x1b[36m⊙ Installing WIDDX Nexus dependencies...\x1b[0m');
        const installResult = spawnSync(pythonExe, ['-m', 'pip', 'install', '--quiet', '-e', `${projectRoot}[api]`], { stdio: 'inherit' });
        if (installResult.status !== 0) {
            console.error('\x1b[31m✗ Failed to install python packages.\x1b[0m');
            process.exit(1);
        }
        console.log('\x1b[32m✓ WIDDX Python environment successfully configured!\x1b[0m\n');
    }

    // Determine target entrypoint based on binary script or arguments
    const binName = path.basename(process.argv[1]);
    let pythonArgs = [];

    if (binName.endsWith('-tui') || process.argv.includes('--tui')) {
        pythonArgs = ['-c', 'from tui.app import run_tui; run_tui()'];
    } else if (binName.endsWith('-web') || process.argv.includes('--web')) {
        pythonArgs = ['-m', 'scripts.web_app'];
    } else if (binName.endsWith('-api') || process.argv.includes('--api')) {
        pythonArgs = ['-m', 'scripts.api_server'];
    } else {
        // Default CLI run
        pythonArgs = ['-c', 'from core.cli import run; run()'];
    }

    // Filter and pass arguments
    const extraArgs = process.argv.slice(2).filter(arg => !['--tui', '--web', '--api'].includes(arg));
    pythonArgs.push(...extraArgs);

    // Set Environment variables
    const env = { 
        ...process.env, 
        WIDDX_ROOT: projectRoot 
    };

    // Run the python application (stdio: inherit keeps full interactive TTY)
    const child = spawn(pythonExe, pythonArgs, { stdio: 'inherit', env });

    child.on('exit', (code) => {
        process.exit(code ?? 0);
    });
}

main().catch(err => {
    console.error('\x1b[31mUnexpected Error:\x1b[0m', err);
    process.exit(1);
});
