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
import asyncio
import subprocess
from typing import Tuple, Any
from core.config import Settings
from schema.reporting import ReportCreationStatus
from .util import ReportCreatorBase

__author__ = "Lukas Reiter"
__copyright__ = "Copyright (C) 2024 Lukas Reiter"
__license__ = "GPLv3"


class PdfLatexCompilationException(Exception):
    def __init__(self, message):
        super().__init__(message)


class ReportCreator(ReportCreatorBase):
    """
    This class is responsible for creating PDFs.
    """
    def __init__(
            self,
            tex_file: str,
            title: Any,
            **kwargs
    ):
        super().__init__(**kwargs)
        self.title = str(title)
        self.pdflatex = self.settings.pdflatex_file
        self.pdflatex_timeout = self.settings.pdflatex_timeout
        self.pdflatex_iterations = self.settings.pdflatex_iterations
        self.tex_file = tex_file
        self.pdf_file = f"{os.path.splitext(tex_file)[0]}.pdf"
        self.log_file = f"{os.path.splitext(tex_file)[0]}.log"
        path, file = os.path.split(tex_file)
        self.pdf_file = os.path.join(path, f"{os.path.splitext(file)[0]}.pdf")
        self.stdout = ""
        self.stderr = ""

    async def _create(self):
        """
        Creates the LaTex sources based on the given data.
        """
        # Launch the pdflatex process
        arguments = list(self.settings.pdflatex_arguments)
        arguments += [
            "-no-shell-escape",
            "-no-shell-restricted",
            "-interaction=nonstopmode",
            "-output-directory",
            self.work_dir,
            self.tex_file,
        ]
        self._logger.debug(f"Running pdflatex with arguments: {' '.join(arguments)}")
        process = await asyncio.create_subprocess_exec(
            self.pdflatex, *arguments,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.work_dir
        )
        await asyncio.wait_for(process.communicate(), timeout=self.pdflatex_timeout)
        # Cancel the task to write newlines after the process finishes
        if not os.path.isfile(self.pdf_file):
            raise PdfLatexCompilationException(f"PDF file '{self.pdf_file}' was not found.")
        if os.stat(self.pdf_file).st_size == 0:
            raise PdfLatexCompilationException(f"PDF file '{self.pdf_file}' is empty.")

    async def create(self):
        """
        Creates the LaTex sources based on the given data.
        """
        if not os.path.isfile(self.pdflatex):
            raise FileNotFoundError(f"pdflatex file '{self.pdflatex}' not found.")
        for i in range(self.pdflatex_iterations):
            await self.notify(
                message=f"Compiling PDF file for {self.title} ({i + 1}/{self.pdflatex_iterations})",
                status=ReportCreationStatus.generating
            )
            await self._create()

    def get_pdf(self) -> bytes:
        """
        Returns the content of the created PDF file.
        """
        with open(self.pdf_file, "rb") as file:
            return file.read()

    def get_log(self) -> bytes | None:
        """
        Returns the content of the created LOG file.
        """
        if not os.path.isfile(self.log_file):
            return None
        with open(self.log_file, "rb") as file:
            return file.read()

    @staticmethod
    def check(settings: Settings):
        """
        Checks prerequisites for creating PDF files.
        """
        if not os.path.isfile(settings.pdflatex_file):
            raise FileNotFoundError(f"pdflatex file '{settings.pdflatex_file}' not found.")
