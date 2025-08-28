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
import re
import shutil
import logging
import tempfile
import platform
from typing import Dict, Any, List, Callable
from core.config import Settings
from schema import ReportGenerationInfo
from schema.user import ReportRequestor
from schema.logging import InjectingFilter
from schema.reporting import ReportCreationStatus
from schema.reporting.report_language import ReportLanguageReport

__author__ = "Lukas Reiter"
__copyright__ = "Copyright (C) 2024 Lukas Reiter"
__license__ = "GPLv3"


class ReportCreatorBase:
    """
    Base class used for creating reports.
    """

    def __init__(
            self,
            settings: Settings,
            info: ReportGenerationInfo,
            work_dir: str,
            notify: Callable[[ReportRequestor, str, ReportCreationStatus, List[Any] | None], Callable]
    ):
        self.notify = notify
        self.settings = settings
        self.info = info
        self.requestor = info.requestor
        self.project = info.project
        self.latest_version_info = self.project.report.versions[-1] if self.project.report.versions else None
        self.report_classification = self.settings.report_classification
        self.work_dir = work_dir
        self.work_abspath = os.path.abspath(work_dir)
        self._logger = logging.getLogger(__name__)
        self._logger.addFilter(InjectingFilter(self.info.requestor))
        self._placeholders = None
        self._re_numbering = {
            r"([\s234567890]1)(st)": "\\1$^{st}$",
            r"([\s234567890]2)(nd)": "\\1$^{nd}$",
            r"([\s234567890]3)(rd)": "\\1$^{nd}$",
            r"((\s11)|(\s12)|(\s13)|([4567890]))(th)": "\\1$^{th}$"
        }
        self.pre_placeholder_pattern = re.compile(r"\{\{\.(\w+)(?::([\w\\\.:\-\s=\(\),;]+))?\}\}")
        self._is_windows = platform.system().lower() == "windows"

    @property
    def report(self):
        return self.project.report

    @property
    def placeholders(self) -> Dict[str, str]:
        """
        This method returns the placeholders.
        """
        def get_date(x: str):
            return f"{x:%B %#d, %Y}" if self._is_windows else f"{x:%B %-d, %Y}"
        if not self._placeholders:
            self._placeholders = {
                "classification": self.report_classification,
                "project_id": self.project.project_id,
                "project_name": self.project.name,
                "project_type": self.project.project_type.name.replace("_", " ").lower(),
                "project_start_date": f"{self.project.start_date:%B %-d, %Y}",
                "vulnerability_counts": self.severity_distribution_str,
                "application_names": self.join_list(
                    self.project.report.report_language,
                    self.project.applications,
                    join_fn=lambda language, item: f"{item.name} ({item.application_id})"
                ) or "n/a",
                "test_reasons": self.join_list(
                    self.project.report.report_language,
                    self.project.reasons,
                    join_fn=lambda language, item: item.name,
                    separator=" "
                ) or "n/a",
                "test_environments": self.join_list(
                    self.project.report.report_language,
                    self.project.environments,
                    join_fn=lambda language, item: item.name
                ) or "n/a",
                "assessors": self.assessors,
                "test_location": self.project.location.name,
            }
            if self.file_name:
                self._placeholders["pdf_file_name"] = self.pdf_file_name
                self._placeholders["xlsx_file_name"] = self.xlsx_file_name
            if self.testing_days:
                self._placeholders["test_days"] = str(self.testing_days)
            if self.latest_version_info:
                self._placeholders["report_version"] = str(self.latest_version_info.version)
                self._placeholders["report_status"] = self.latest_version_info.status.name.capitalize()
                self._placeholders["delivery_date"] = self.delivery_date
            if self.project.end_date:
                self._placeholders["project_end_date"] = get_date(self.project.end_date)
                self._placeholders["test_period"] = self.test_period
            if self.project.lead_tester:
                self._placeholders["lead_tester_name"] = self.project.lead_tester.full_name
            if self.project.manager:
                self._placeholders["manager_name"] = self.project.manager.full_name
            if self.project.provider:
                self._placeholders["provider_name"] = self.project.provider.name
                self._placeholders["provider_short"] = self.project.provider.abbreviation
                self._placeholders["provider_address"] = self.project.provider.address
            if self.project.provider:
                self._placeholders["customer_name"] = self.project.customer.name
                self._placeholders["customer_short"] = self.project.customer.abbreviation
                self._placeholders["customer_address"] = self.project.customer.address
            self._placeholders = {key: str(value) for key, value in self._placeholders.items()}
        return self._placeholders

    @property
    def file_name(self) -> str:
        """
        Returns the file name.
        """
        result = None
        if self.latest_version_info and self.project:
            report_version = self.latest_version_info.version
            report_status = self.latest_version_info.status.name.capitalize()
            result = f"{self.project.project_id}\\_{report_status}-Report\\_v{report_version}"
        return result

    @property
    def pdf_file_name(self) -> str:
        """
        Returns the PDF file name.
        """
        if result := self.file_name:
            result += ".pdf"
        return result

    @property
    def xlsx_file_name(self) -> str:
        """
        Returns the file name.
        """
        if result := self.file_name:
            result += ".xlsx"
        return result

    @property
    def test_period(self) -> str:
        """
        This method returns the test range.
        """
        if not self.project.end_date:
            return "Error: No end date set."
        if self.project.start_date.year == self.project.end_date.year:
            result = f"{self.project.start_date:%B %#d}" if self._is_windows else f"{self.project.start_date:%B %-d}"
        else:
            result = (f"{self.project.start_date:%B %#d, %Y}"
                      if self._is_windows else f"{self.project.start_date:%B %-d, %Y}")
        result += " to "
        if (
                self.project.start_date.year == self.project.end_date.year and
                self.project.start_date.month == self.project.end_date.month
        ):
            result += f"{self.project.end_date:%#d, %Y}" if self._is_windows else f"{self.project.end_date:%-d, %Y}"
        else:
            result += (f"{self.project.end_date:%B %#d, %Y}"
                       if self._is_windows else f"{self.project.end_date:%B %-d, %Y}")
        return result

    @property
    def severity_distribution_str(self) -> str:
        """
        This method returns the severity distribution as a string.
        """
        severity_distribution = self.report.severity_distribution_list
        critical, high, medium, low = severity_distribution
        values = []
        vulnerability_count = sum(severity_distribution)
        if critical:
            values.append(f"{critical} critical-")
        if high:
            values.append(f"{high} high-")
        if medium:
            values.append(f"{medium} medium-")
        if low:
            values.append(f"{low} low-")
        if len(values) == 0:
            result = ""
        elif len(values) == 1:
            result = f"{values[0]}severity issue{'s' if vulnerability_count > 1 else ''}"
        else:
            result = f"{', '.join(values[:-1])} and {values[-1]}severity issues"
        return result

    @property
    def testing_days(self) -> int | None:
        if self.project.start_date and self.project.end_date:
            return (self.project.end_date - self.project.start_date).days + 1
        return None

    @property
    def assessors(self):
        """
        This method returns the assessors.
        """
        assessors = []
        if self.project.lead_tester:
            assessors.append(self.project.lead_tester.full_name)
        assessors = sorted( assessors + [item.full_name for item in self.project.testers])
        return self.join_list(
            self.project.report.report_language,
            assessors,
            join_fn=lambda language, item: item
        )

    @property
    def delivery_date(self):
        """
        This method returns the delivery date.
        """
        return (f"{self.latest_version_info.report_date:%B %#d, %Y}"
                if self._is_windows else f"{self.latest_version_info.report_date:%B %-d, %Y}")

    @staticmethod
    def join_list(
            language: ReportLanguageReport,
            items: List[Any],
            join_fn: Callable[[ReportLanguageReport, Any], str],
            separator: str = ", "
    ) -> str:
        """
        This method joins a list of items with a separator.
        """
        if language.language_code != "en":
            raise ValueError("Only English is supported.")
        result = [join_fn(language, item) for item in items]
        if len(result) == 0:
            return ""
        elif len(result) == 1:
            return result[0]
        elif len(result) == 2:
            return f"{result[0]} and {result[1]}"
        else:
            return f"{separator.join(result[:-1])}, and {result[-1]}"

    @staticmethod
    def create_zip(source: str) -> bytes | None:
        """
        This method creates and returns a ZIP file.
        """
        if not os.path.isdir(source):
            raise NotADirectoryError(f"The source '{source}' is not a directory.")
        with tempfile.NamedTemporaryFile(suffix=".zip") as file:
            file_name = os.path.splitext(file.name)[0]
            shutil.make_archive(file_name, "zip", source)
            with open(file.name, "rb") as content:
                result = content.read()
        return result

    def replace_placeholders(
            self,
            report_text: str,
            placeholder_pattern: re.Pattern,
            placeholder_values: Dict[str, str],
            placeholder_fn: Callable[[str, Dict[str, str], str, str | None], str | None]
    ) -> str:
        """
        Replaces placeholders in the report text with values from the placeholder dictionary.
        Supports named parameters.

        :param report_text: str, the report text containing placeholders.
        :param placeholder_pattern: re.Pattern, the pattern to match placeholders.
        :param placeholder_values: dict, dictionary containing placeholder values.
        :param placeholder_fn: function, a function that generates the final value for placeholders.
        :return: str, the final text with placeholders replaced.
        """
        def parse_parameters(params: str) -> Dict[str, str]:
            """
            Parses the parameters of a placeholder.
            """
            param_dict = {}
            try:
                if params:
                    for param in [item.strip() for item in params.split(';')]:
                        key, value = param.split('=')
                        param_dict[key.strip()] = value.strip()
            except ValueError as ex:
                self._logger.exception(ex)
                raise ValueError(f"Invalid parameter format due to missing semicolon in: {params}")
            return param_dict

        def replacement(match: re.Match) -> str:
            placeholder_name = match.group(1).replace("\\", "")
            params = parse_parameters(match.group(2))
            if placeholder_name not in placeholder_values:
                self._logger.debug(f"Placeholder {placeholder_name} cannot be resolved via list: "
                                   f"{placeholder_values.keys}")
            final_name = placeholder_values.get(placeholder_name)
            return placeholder_fn(placeholder_name, params, match.group(0), final_name)
        return placeholder_pattern.sub(replacement, report_text)

    def replace_placeholders_only_func(
            self,
            placeholder_name: str,
            params: Dict[str, str],
            matched_string: str,
            final_name: str | None
    ) -> str:
        """
        Default placeholder function that replaces placeholders with the final value.
        :param placeholder_name: str, the placeholder name.
        :param params: dict, dictionary containing placeholder parameters.
        :param matched_string: str, the matched placeholder string.
        :param final_name: str, the final value for the placeholder.
        :return:
        """
        return final_name if final_name else matched_string

    def replace_placeholders_only_with_latex_escape_func(
            self,
            placeholder_name: str,
            params: Dict[str, str],
            matched_string: str,
            final_name: str | None
    ) -> str:
        """
        Default placeholder function that replaces placeholders with the final value.
        :param placeholder_name: str, the placeholder name.
        :param params: dict, dictionary containing placeholder parameters.
        :param matched_string: str, the matched placeholder string.
        :param final_name: str, the final value for the placeholder.
        :return:
        """
        result = matched_string.replace("_", "\\_") \
            .replace("{", "\\{") \
            .replace("}", "\\}")
        return final_name if final_name else result

    def post_processing_func(self, content: str) -> str:
        """
        Placeholder function that performs post-processing on the final value.
        :return:
        """
        # Make sure URLs are underlined (at the moment Latex commands \url and \href are considered)
        result = re.sub("\\\\href[\\s\\n]*\\{", "\\\\slink{", content)
        for pattern, repl in self._re_numbering.items():
            result = re.sub(pattern=pattern, repl=repl, string=result)
        # Make sure that 1st, 2nd, 3rd, 4th, ... are formatted correctly
        for pattern, repl in self._re_numbering.items():
            result = re.sub(pattern=pattern, repl=repl, string=result)
        return result

    def create(self):
        """
        Creates the report.
        """
        raise NotImplementedError()

    def get_content(self) -> bytes:
        """
        Returns the report content.
        """
        raise NotImplementedError()

    @staticmethod
    def check(self):
        """
        Checks prerequisites for creating the report.
        """
        raise NotImplementedError()
