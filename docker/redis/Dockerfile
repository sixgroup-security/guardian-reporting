FROM redis:latest
RUN groupadd -g 1001 -r guardian \
    && useradd --no-log-init -u 1001 -r -g guardian guardian
COPY docker/redis/redis.conf docker/redis/redis-dev.conf /usr/local/etc/redis/
RUN chown -R guardian:guardian /data
USER guardian
