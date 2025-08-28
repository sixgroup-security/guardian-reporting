# This file is part of Guardian.
#
# Guardian is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Guardian is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Guardian. If not, see <https://www.gnu.org/licenses/>.

import os
from dotenv import load_dotenv
from pathlib import Path
from schema import SettingsBase
from schema.reporting.report_template import ReportTemplateFileVersion

__author__ = "Lukas Reiter"
__copyright__ = "Copyright (C) 2024 Lukas Reiter"
__license__ = "GPLv3"

# TODO: Load environments variables depending on prod or test environment.
APP_DIRECTORY = Path(__file__).parent.parent
load_dotenv(APP_DIRECTORY / ".env")
load_dotenv(APP_DIRECTORY / ".env.db")


class Settings(SettingsBase):
    """
    This class manages the settings of the application.
    """
    def __init__(self):
        super().__init__()
        self.data_directory = os.getenv("DATA_DIRECTORY")
        self.latex_template_directory = os.getenv("LATEX_TEMPLATE_DIRECTORY")
        self.latex_template_file = os.getenv("LATEX_TEMPLATE_FILE")
        self.latex_command_whitelist = sorted([
            item.strip().lower() for item in os.getenv("LATEX_COMMAND_WHITELIST", "").split(",")
        ])
        self.worker_threads = int(os.getenv("WORKER_THREADS", 1))
        self.excel_template_file = os.getenv("EXCEL_TEMPLATE_FILE")
        self.excel_sheet_name = os.getenv("EXCEL_TEMPLATE_SHEET")
        self.excel_table_name = os.getenv("EXCEL_TABLE_NAME")
        self.excel_template_row = int(os.getenv("EXCEL_TEMPLATE_ROW", 2))
        self.report_classification = os.getenv("REPORT_CLASSIFICATION", "")
        self.pandoc_arguments = os.getenv("PANDOC_ARGUMENTS", "").split()
        self.pdflatex_file = os.getenv("PDFLATEX_FILE")
        self.pdflatex_arguments = os.getenv("PDFLATEX_ARGUMENTS", "").split()
        self.pdflatex_timeout = int(os.getenv("PDFLATEX_EXECUTION_TIMEOUT"), 30)
        self.pdflatex_iterations = int(os.getenv("PDFLATEX_EXECUTION_TIMES", 3))
        self.cvss_base_url = os.getenv("CVSS_BASE_URL", "https://www.first.org/cvss/calculator/3.1")
        self.cvss_version = os.path.basename(self.cvss_base_url)
        self.cvss_definitions_url = os.getenv("CWE_DEFINITIONS_URL")

    def get_latex_template_directory(self, version: ReportTemplateFileVersion) -> str:
        return os.path.join(self.data_directory, version.name, self.latex_template_directory)

    def get_latex_template_file(self, version: ReportTemplateFileVersion) -> str:
        base_dir = self.get_latex_template_directory(version)
        return os.path.join(base_dir, self.latex_template_file)

    def get_excel_template_file(self, version: ReportTemplateFileVersion) -> str:
        return os.path.join(self.data_directory, version.name, self.excel_template_file)


settings = Settings()
