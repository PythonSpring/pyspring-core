import json
import os
from typing import ClassVar, Optional, Type

from loguru import logger
from pydantic import BaseModel

from py_spring_core.commons.config_file_template_generator.templates import (
    app_config_template,
    app_properties_template,
)
from py_spring_core.core.application.application_config import ApplicationConfig


class ConfigFileTemplateGenerator:
    """
    Generates template configuration files for the application, including the app config and application properties files.
    The `ConfigFileTemplateGenerator` class is responsible for generating the template configuration files if they do not already exist in the target directory.
    It uses the `ApplicationConfigRepository` and `ApplicationPropertiesRepository` to load the template configurations and save them to the target directory.
    The `generate_app_config_file_template_if_not_exists` method checks if the app config file already exists in the target directory, and if not, generates the template file.
    The `generate_app_properties_file_template_if_not_exists` method checks if the application properties file already exists in the target directory, and if not, generates the template file.
    """

    APP_CONFIG_FILE_NAME: ClassVar[str] = "app-config.json"
    APP_PROPERTIES_NAME: ClassVar[str] = "application-properties.json"

    def __init__(self, target_file_dir: str) -> None:
        self.target_file_dir = target_file_dir

    def _is_valid_template(
        self, template: dict, validator_cls: Type[BaseModel]
    ) -> bool:
        try:
            validator_cls.model_validate(template)
            return True
        except Exception as e:
            return False

    def _save_template(
        self,
        target_file: str,
        template: dict,
        validator_cls: Optional[Type[BaseModel]] = None,
    ) -> None:
        with open(target_file, "w") as file:
            if validator_cls is None:
                file.write(json.dumps(template, indent=4))
            else:
                is_valid = self._is_valid_template(template, validator_cls)
                if is_valid:
                    template_instance = validator_cls.model_validate(template)
                    file.write(template_instance.model_dump_json(indent=4))

    def generate_app_config_file_template_if_not_exists(self) -> None:
        target_file = os.path.join(self.target_file_dir, self.APP_CONFIG_FILE_NAME)

        if os.path.exists(target_file):
            logger.info(f"[APP CONFIG ALREADY EXISTS] {target_file} already exists")
            return
        self._save_template(target_file, app_config_template, ApplicationConfig)
        logger.success(
            f"[APP CONFIG GENERATED] App config file not exists, {target_file} generated"
        )

    def generate_app_properties_file_template_if_not_exists(self) -> None:
        target_file = os.path.join(self.target_file_dir, self.APP_PROPERTIES_NAME)
        if os.path.exists(target_file):
            logger.info(f"[APP PROPERTIES ALREADY EXISTS] {target_file} already exists")
            return
        self._save_template(target_file, app_properties_template)
        logger.success(
            f"[APP PROPERTIES GENERATED] App properties file not exists, {target_file} generated"
        )
