import sys
import os
import shutil
import platform
import json
import urllib.request
import stat

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

def detect_init_system():
    if os.path.exists("/sbin/openrc") or os.path.exists("/etc/init.d"):
        return "openrc"
    elif shutil.which("systemctl") is not None and os.path.exists("/run/systemd/system/"):
        return "systemd"
    else:
        return "unknown"

def load_paths(init_system):
    home_dir = os.environ['HOME']
    user_install = sys.argv.count("--user") > 0
    
    if init_system == "systemd":
        if user_install:
            return [True, home_dir, f'{home_dir}/.local/bin', f'{home_dir}/.config/komodo', f'{home_dir}/.config/systemd/user']
        else:
            return [False, home_dir, "/usr/local/bin", "/etc/komodo", "/etc/systemd/system"]
    else:  # OpenRC
        if user_install:
            print("Warning: OpenRC doesn't fully support user services. Installing system-wide is recommended.")
            return [True, home_dir, f'{home_dir}/.local/bin', f'{home_dir}/.config/komodo', "/etc/init.d"]
        else:
            return [False, home_dir, "/usr/local/bin", "/etc/komodo", "/etc/init.d"]

def copy_binary(init_system, user_install, bin_dir, version):
    if init_system == "openrc":
        if not user_install:
            os.popen('rc-service periphery stop 2>/dev/null')
    else:  # systemd
        user = " --user" if user_install else ""
        os.popen(f'systemctl{user} stop periphery')

    if not os.path.isdir(bin_dir):
        os.makedirs(bin_dir)

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
    config_file = f'{config_dir}/periphery.config.toml'
    if os.path.isfile(config_file):
        print("config already exists, skipping...")
        return
    
    print(f'creating config at {config_file}')
    if not os.path.isdir(config_dir):
        os.makedirs(config_dir)
    
    print(os.popen(f'curl -sSL https://raw.githubusercontent.com/mbecker20/komodo/main/config/periphery.config.toml > {config_dir}/periphery.config.toml').read())

def create_openrc_service(home_dir, bin_dir, config_dir, service_dir):
    service_file = f'{service_dir}/periphery'
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
		export HOME="{home_dir}"
	}}
	"""

    with open(service_file, "w") as f:
        f.write(service_content)
    os.chmod(service_file, 0o755)
    print(f"Created OpenRC service file at {service_file}")
    
def copy_service_file(init_system, home_dir, bin_dir, config_dir, service_dir, user_install):
    force_service_recopy = sys.argv.count("--force-service-file") > 0
    
    if init_system == "openrc":
        service_file = f'{service_dir}/periphery'
    else if init_system == "systemd":
        service_file = f'{service_dir}/periphery.service'
    
    if os.path.isfile(service_file):
        if force_service_recopy:
            print("deleting existing service file")
            os.remove(service_file)
        else:
            print("service file already exists, skipping...")
            return
    
    print(f'creating service file at {service_file}')
    if not os.path.isdir(service_dir):
        os.makedirs(service_dir)

    if init_system == "openrc":
        create_openrc_service(home_dir, bin_dir, config_dir, service_dir)
    else:  # systemd
        service_content = (
            "[Unit]\n"
            "Description=Agent to connect with Komodo Core\n"
            "\n"
            "[Service]\n"
            f'Environment="HOME={home_dir}"\n'
            f'ExecStart=/bin/sh -lc "{bin_dir}/periphery --config-path {config_dir}/periphery.config.toml"\n'
            "Restart=on-failure\n"
            "TimeoutStartSec=0\n"
            "\n"
            "[Install]\n"
            "WantedBy=default.target"
        )
        with open(service_file, "w") as f:
            f.write(service_content)

        if init_system == "systemd":
            user = " --user" if user_install else ""
            os.popen(f'systemctl{user} daemon-reload')

def start_service(init_system, user_install):
    print("starting periphery...")
    if init_system == "openrc":
        if not user_install:
            print(os.popen('rc-service periphery start').read())
            print('\nTo enable service at boot:')
            print('  rc-update add periphery default')
            print('\nTo check service status:')
            print('  rc-service periphery status')
            print('\nTo manage service:')
            print('  rc-service periphery start|stop|restart')
    else:  # systemd
        user = " --user" if user_install else ""
        print(os.popen(f'systemctl{user} start periphery').read())
        print(f'\nNote. Use "systemctl{user} status periphery" to check status')
        print(f'Note. Use "systemctl{user} enable periphery" to enable on boot')

def main():
    print("=====================")
    print(" PERIPHERY INSTALLER ")
    print("=====================")

    init_system = detect_init_system()
    if init_system == "unknown":
        print("No supported init system (OpenRC/systemd) found. Exiting.")
        sys.exit(1)

    print(f"Detected init system: {init_system}")
    version = load_version()
    [user_install, home_dir, bin_dir, config_dir, service_dir] = load_paths(init_system)
 
    print(f'version: {version}')
    print(f'user install: {user_install}')
    print(f'home dir: {home_dir}')
    print(f'bin dir: {bin_dir}')
    print(f'config dir: {config_dir}')
    print(f'service file dir: {service_dir}')

    copy_binary(init_system, user_install, bin_dir, version)
    copy_config(config_dir)
    copy_service_file(init_system, home_dir, bin_dir, config_dir, service_dir, user_install)
    start_service(init_system, user_install)

    print("\nFinished periphery setup.")

if __name__ == "__main__":
    main()