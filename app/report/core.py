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
import json
import shutil
import logging
import pathlib
import tempfile
from core.config import settings
from report import notify_user
from schema import SessionLocal
from schema.logging import InjectingFilter
from schema.project import Report, ReportGenerationInfo, ReportRequestType
from schema.reporting.report_section_management.vulnerability import Vulnerability
from schema.reporting.report_version import ReportVersion, ReportCreationStatus
from .pdf import ReportCreator as PdfReportCreator
from .excel import ReportCreator as ExcelReportCreator
from .latex import ReportCreator as LatexReportCreator
from .latex import VulnerabilityCreator as LatexVulnerabilityCreator
from sqlalchemy import and_
from sqlalchemy.orm import Session

__author__ = "Lukas Reiter"
__copyright__ = "Copyright (C) 2024 Lukas Reiter"
__license__ = "GPLv3"

APP_PATH = pathlib.Path(__file__).parent.parent


def check_setup():
    """
    This function checks if the necessary directories and files are present.
    """
    PdfReportCreator.check(settings)
    LatexReportCreator.check(settings)
    ExcelReportCreator.check(settings)


async def process_report_creation(
        session: Session,
        images_dir: str,
        work_dir: str,
        logger: logging.Logger,
        info: ReportGenerationInfo
):
    """
    Processes the report creation.
    """
    async def notify(
        **kwargs
    ):
        """
        Helper function for notifying the user about the report creation progress.
        """
        await notify_user(
            requestor=info.requestor,
            **kwargs
        )

    report_id = info.project.report.id
    if info.type == ReportRequestType.report:
        report_version_id = info.project.report.versions[-1].version
        query_key = ["report", {"report": str(report_id)}, "overview", "version"]
        report_version = session.query(ReportVersion) \
            .join(Report) \
            .filter(and_(
                Report.id == report_id,
                ReportVersion.version == report_version_id
            )
        ).one()
        report_version.creation_status = ReportCreationStatus.generating
        await notify(
            message=f"Report creation started for version: v{report_version_id}.",
            status=ReportCreationStatus.generating,
            query_key=query_key
        )
        session.commit()
        # 1. Create Excel file
        try:
            with tempfile.NamedTemporaryFile(suffix=".xlsx") as excel_file:
                creator = ExcelReportCreator(
                    notify=notify,
                    excel_file=excel_file.name,
                    settings=settings,
                    work_dir=work_dir,
                    info=info
                )
                creator.create()
                report_version.xlsx = creator.get_xlsx()
                session.commit()
            await notify(
                message=f"Excel report was successfully created for version: v{report_version_id} ",
                status=ReportCreationStatus.generating,
                query_key=query_key
            )
        except Exception as ex:
            report_version.creation_status = ReportCreationStatus.failed
            logger.exception(ex)
            await notify(
                message=f"Excel report creation was unsuccessful for version: v{report_version_id}",
                status=ReportCreationStatus.failed,
                query_key=query_key
            )
        # Create Latex report
        latex_creator = LatexReportCreator(
            notify=notify,
            settings=settings,
            work_dir=work_dir,
            images_dir=images_dir,
            info=info
        )
        try:
            latex_creator.create()
            report_version.tex = latex_creator.get_zip()
            session.commit()
            await notify(
                message=f"Latex files were successfully created for version: v{report_version_id}",
                status=ReportCreationStatus.generating,
                query_key=query_key
            )
        except Exception as ex:
            report_version.creation_status = ReportCreationStatus.failed
            logger.exception(ex)
            await notify(
                message=f"PDF file creation failed for version: v{report_version_id}",
                status=ReportCreationStatus.failed,
                query_key=query_key
            )
        try:
            # Create PDF report
            pdf_creator = PdfReportCreator(
                title=f"version: v{report_version_id}",
                notify=notify,
                settings=settings,
                tex_file=latex_creator.tex_file,
                work_dir=work_dir,
                info=info
            )
            await pdf_creator.create()
            report_version.pdf = pdf_creator.get_pdf()
            # We don't need the logs, if building was successful.
            report_version.pdf_log = None # pdf_creator.get_log()
            report_version.creation_status = ReportCreationStatus.successful
            session.commit()
            await notify(
                message=f"PDF file was successfully created for version: v{report_version_id}",
                status=ReportCreationStatus.successful,
                query_key=query_key
            )
        except Exception as ex:
            report_version.creation_status = ReportCreationStatus.failed
            try:
                report_version.pdf_log = pdf_creator.get_log()
                session.commit()
            except Exception as ex1:
                logger.exception(ex1)
            logger.exception(ex)
            await notify(
                message=f"PDF file creation failed for version: v{report_version_id}",
                status=ReportCreationStatus.failed,
                query_key=query_key
            )
    elif info.type == ReportRequestType.vulnerability:
        for vulnerability_id in info.vulnerabilities:
            # query_key = ["vulnerability", str(vulnerability_id)]
            vulnerability = session.query(Vulnerability).filter_by(id=vulnerability_id).one()
            vulnerability.creation_status = ReportCreationStatus.generating
            await notify(
                message=f"PDF file creation started for vulnerability: {vulnerability.vulnerability_id_str}",
                status=ReportCreationStatus.generating
            )
            # Create Latex report
            try:
                latex_creator = LatexVulnerabilityCreator(
                    notify=notify,
                    settings=settings,
                    work_dir=work_dir,
                    images_dir=images_dir,
                    vulnerability=vulnerability,
                    info=info
                )
                latex_creator.create()
                vulnerability.tex = latex_creator.get_zip()
                await notify(
                    message=f"Latex files were successfully created for vulnerability: "
                            f"{vulnerability.vulnerability_id_str}",
                    status=ReportCreationStatus.generating,
                )
                # Create PDF report
                pdf_creator = PdfReportCreator(
                    title=f"vulnerability: {vulnerability.vulnerability_id_str}",
                    notify=notify,
                    settings=settings,
                    tex_file=latex_creator.tex_file,
                    work_dir=work_dir,
                    info=info
                )
                await pdf_creator.create()
                vulnerability.pdf = pdf_creator.get_pdf()
                # We don't need the logs, if building was successful.
                vulnerability.pdf_log = None # pdf_creator.get_log()
                vulnerability.creation_status = ReportCreationStatus.successful
                session.commit()
                await notify(
                    message=f"PDF file was successfully created for vulnerability: "
                            f"{vulnerability.vulnerability_id_str}",
                    status=ReportCreationStatus.successful,
                    # We cannot enable the query_key here, because this will refresh the page and potentially overwrite
                    # newly made changes.
                    # query_key=query_key
                )
            except Exception as ex:
                vulnerability.creation_status = ReportCreationStatus.failed
                try:
                    vulnerability.pdf_log = pdf_creator.get_log()
                    session.commit()
                except Exception as ex1:
                    logger.exception(ex1)
                logger.exception(ex)
                await notify(
                    message=f"PDF file creation failed for vulnerability: {vulnerability.vulnerability_id_str}",
                    status=ReportCreationStatus.failed,
                    # We cannot enable the query_key here, because this will refresh the page and potentially overwrite
                    # newly made changes.
                    # query_key=query_key
                )


async def process_json(data: str):
    """
    This function processes the report version JSON object and creates the Tex and PDF file out of it.
    """
    # This exception handler is necessary to catch any exceptions that might occur during the report parsing. At this
    # time we do not have a user context, so we cannot log user-specific information.
    status = ReportCreationStatus.successful
    try:
        json_object = json.loads(data)
        info = ReportGenerationInfo(**json_object)
        # We set up the logging configuration
        logger = logging.getLogger(__name__)
        logger.addFilter(InjectingFilter(info.requestor))
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                # temp_dir = "/tmp/guardian"
                logger.info("Start creating reports...")
                images_dir = "images"
                latex_dir_name = os.path.basename(settings.latex_template_directory)
                latex_destination_dir = os.path.join(temp_dir, latex_dir_name)
                images_fullpath = os.path.join(latex_destination_dir, images_dir)
                shutil.copytree(
                    settings.get_latex_template_directory(info.project.report.version),
                    latex_destination_dir
                )
                if not os.path.isdir(images_fullpath):
                    os.mkdir(images_fullpath)
                with SessionLocal() as session:
                    await process_report_creation(
                        session=session,
                        images_dir=images_dir,
                        work_dir=latex_destination_dir,
                        logger=logger,
                        info=info
                    )
                    session.commit()
            except Exception as ex:
                logger.exception(ex)
                status = ReportCreationStatus.failed
        logger.info(f"Report creation {status.name}.")
    except Exception as ex:
        logger = logging.getLogger(__name__)
        logger.exception(ex)
