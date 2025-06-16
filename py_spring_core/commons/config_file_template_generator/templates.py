from typing import Any

app_config_template = {
    "app_src_target_dir": "./src",
    "server_config": {"host": "0.0.0.0", "port": 8080, "enabled": True},
    "properties_file_path": "./application-properties.json",
    "loguru_config": {"log_file_path": "./logs/app.log", "log_level": "DEBUG"},
    "type_checking_mode": "strict",
}

app_properties_template: dict[str, Any] = {}
