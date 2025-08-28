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

import schema
import logging
from typing import List, Any
from schema import ReportRequestor, NotifyUser
from schema.database.redis_client import publish
from schema.reporting import ReportCreationStatus
from schema.util import StatusEnum, StatusMessage

__author__ = "Lukas Reiter"
__copyright__ = "Copyright (C) 2024 Lukas Reiter"
__license__ = "GPLv3"

logger = logging.getLogger(__name__)


async def notify_user(
        requestor: ReportRequestor,
        message,
        status: ReportCreationStatus,
        query_key: List[Any] | None = None
) -> None:
    """
    Notifies a user about the status of the report creation.
    """
    try:
        if status == ReportCreationStatus.generating:
            severity = StatusEnum.info
            status_code = 200
        elif status == ReportCreationStatus.successful:
            severity = StatusEnum.success
            status_code = 200
        elif status == ReportCreationStatus.failed:
            severity = StatusEnum.error
            status_code = 500
        else:
            severity = StatusEnum.info
            status_code = 200
        notify = NotifyUser(
            user=requestor,
            status=StatusMessage(
                message=message,
                severity=severity,
                status=status_code,
                payload={"invalidateQueries": [query_key]} if query_key else None
            )
        )
        await schema.database.redis_client.notify_user(message=notify)
    except Exception as ex:
        logger.exception(ex)
