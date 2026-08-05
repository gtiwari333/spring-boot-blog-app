# Spring Boot Docker image — simple single-stage build.
#
# Build the jar first:
#   mvn package -DskipTests
#
# Then build the Docker image:
#   docker build -t blog-app:4.1.0 .
#
# Or use Cloud Native Buildpacks (no Dockerfile needed):
#   mvn spring-boot:build-image -DskipTests
#   → creates image "blog-app:4.1.0"

FROM eclipse-temurin:25-jre-alpine
WORKDIR /app
RUN addgroup --system javauser && adduser -S -G javauser javauser

VOLUME /tmp
VOLUME /X/attachments

COPY target/dev-4.1.0-app.jar app.jar

USER javauser
# Heap: 128m initial, 256m max — plenty for this blog app
# Use SerialGC — lowest footprint for small workloads
ENTRYPOINT ["java", \
    "-Xms128m", "-Xmx256m", \
    "-XX:+UseSerialGC", \
    "-XX:MaxMetaspaceSize=128m", \
    "-XX:ReservedCodeCacheSize=64m", \
    "-Djava.security.egd=file:/dev/./urandom", \
    "-jar", "/app/app.jar"]
