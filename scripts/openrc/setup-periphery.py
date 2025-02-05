import sys
import os
import shutil
import platform
import json
import urllib.request

def load_version():
    version = ""
    for arg in sys.argv:
        if arg.count("--version") > 0:
            version = arg.split("=")[1]
    if len(version) == 0:
        version = load_latest_version()
    return version

def load_latest_version():
    return json.load(urllib.request.urlopen("https://api.github.com/repos/mbecker20/komodo/releases/latest"))["tag_name"]

def check_openrc():
    """Check if OpenRC is available on the system"""
    return os.path.exists("/sbin/openrc") or os.path.exists("/etc/init.d")

def load_paths():
    """Load installation paths for OpenRC"""
    home_dir = os.environ['HOME']
    user_install = sys.argv.count("--user") > 0
    
    if user_install:
        print("Warning: OpenRC requires root privileges for service management.")
        print("Installing in user directory but service management will be limited.")
        return [
            True,
            home_dir,
            f'{home_dir}/.local/bin',
            f'{home_dir}/.config/komodo',
        ]
    else:
        return [
            False,
            home_dir,
            "/usr/local/bin",
            "/etc/komodo",
        ]

def copy_binary(bin_dir, version):
    """Install the binary"""
    # Attempt to stop any running service
    os.popen('rc-service periphery stop 2>/dev/null')

    # ensure bin_dir exists
    if not os.path.isdir(bin_dir):
        os.makedirs(bin_dir)

    # delete binary if it already exists
    bin_path = f'{bin_dir}/periphery'
    if os.path.isfile(bin_path):
        os.remove(bin_path)

    periphery_bin = "periphery-x86_64"
    arch = platform.machine().lower()
    if arch == "aarch64" or arch == "amd64":
        print("aarch64 detected")
        periphery_bin = "periphery-aarch64"
    else:
        print("using x86_64 binary")

    print(os.popen(f'curl -sSL https://github.com/mbecker20/komodo/releases/download/{version}/{periphery_bin} > {bin_path}').read())
    os.chmod(bin_path, 0o755)

def copy_config(config_dir):
    """Install the configuration file"""
    config_file = f'{config_dir}/periphery.config.toml'
    if os.path.isfile(config_file):
        print("config already exists, skipping...")
        return
    
    print(f'creating config at {config_file}')
    if not os.path.isdir(config_dir):
        os.makedirs(config_dir)
    
    print(os.popen(f'curl -sSL https://raw.githubusercontent.com/mbecker20/komodo/main/config/periphery.config.toml > {config_dir}/periphery.config.toml').read())

def install_service(home_dir, bin_dir, config_dir, user_install):
    """Create and install OpenRC service"""
    if user_install:
        print("Note: Skipping service installation for user install")
        print(f"To run manually: {bin_dir}/periphery --config-path {config_dir}/periphery.config.toml")
        return

    service_dir = "/etc/init.d"
    service_file = f'{service_dir}/periphery'
    
    force_service_recopy = sys.argv.count("--force-service-file") > 0
    if os.path.isfile(service_file) and not force_service_recopy:
        print("service file already exists, skipping...")
        return

    print(f'creating OpenRC service file at {service_file}')
    
    service_content = f"""#!/sbin/openrc-run

name="periphery"
description="Agent to connect with Komodo Core"
command="{bin_dir}/periphery"
command_args="--config-path {config_dir}/periphery.config.toml"
command_background="yes"
pidfile="/run/${{RC_SVCNAME}}.pid"
output_log="/var/log/${{RC_SVCNAME}}.log"
error_log="/var/log/${{RC_SVCNAME}}.error"

depend() {{
    need net
    after logger
}}

start_pre() {{
    checkpath -d -m 0755 -o root:root /run
    checkpath -d -m 0755 -o root:root /var/log
    export HOME="{home_dir}"
}}
"""
    with open(service_file, "w") as f:
        f.write(service_content)
    os.chmod(service_file, 0o755)
    print("OpenRC service installed successfully")

def start_service(user_install):
    """Start and configure the service"""
    if user_install:
        return

    print("\nStarting periphery service...")
    os.popen('rc-service periphery start').read()
    
    print("\nService Management Commands:")
    print("  Check status:   rc-service periphery status")
    print("  Start service:  rc-service periphery start")
    print("  Stop service:   rc-service periphery stop")
    print("  Restart:        rc-service periphery restart")
    print("\nTo enable service on boot:")
    print("  rc-update add periphery default")
    
    print("\nTo view logs:")
    print("  tail -f /var/log/periphery.log")
    print("  tail -f /var/log/periphery.error")

def main():
    print("===========================")
    print(" PERIPHERY OPENRC INSTALLER")
    print("===========================")

    if not check_openrc():
        print("\nError: OpenRC not found on this system")
        print("This installer requires OpenRC to be installed")
        print("\nInstallation aborted.")
        sys.exit(1)

    version = load_version()
    [user_install, home_dir, bin_dir, config_dir] = load_paths()
 
    print(f'\nInstallation Configuration:')
    print(f'Version: {version}')
    print(f'User install: {user_install}')
    print(f'Home directory: {home_dir}')
    print(f'Binary directory: {bin_dir}')
    print(f'Config directory: {config_dir}')

    print("\nInstalling components:")
    copy_binary(bin_dir, version)
    copy_config(config_dir)
    install_service(home_dir, bin_dir, config_dir, user_install)
    start_service(user_install)

    print("\nPeriphery installation complete!")

if __name__ == "__main__":
    main()