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

import asyncio
from io import StringIO
from dotenv import load_dotenv
# We specify the environment to be used.
load_dotenv(stream=StringIO("ENV=prod"))
from core.config import settings
from schema.database.redis_client import subscribe as redis_subscribe
from report.core import process_json, check_setup
# We set up the logging configuration
from schema.logging import *

__author__ = "Lukas Reiter"
__copyright__ = "Copyright (C) 2024 Lukas Reiter"
__license__ = "GPLv3"

logger = logging.getLogger(__name__)


async def consume_messages():
    """
    Consumes and processes messages from the RabbitMQ server.
    """
    logger.info(f"Waiting for messages...")
    try:
        await redis_subscribe(
            username=settings.redis_user_report_read,
            password=settings.redis_password_report_read,
            channel=settings.redis_report_channel,
            callback=process_json
        )
    except Exception as ex:
        logger.exception(ex)


async def main():
    # Check if configuration is correct
    check_setup()
    # Start worker threads
    tasks = [consume_messages() for _ in range(settings.worker_threads)]
    # Await the completion of all tasks
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
