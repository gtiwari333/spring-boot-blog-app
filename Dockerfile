FROM adoptopenjdk/openjdk11
VOLUME /tmp
VOLUME /X/attachments
COPY target/*.jar spring-boot-note-app.jar
ENTRYPOINT ["java","-Djava.security.egd=file:/dev/./urandom","-jar","/spring-boot-note-app.jar"]
