FROM openjdk:17
EXPOSE 8080
WORKDIR /app

# Copy maven executable to the image
COPY mvnw .
COPY .mvn .mvn

# Copy the pom.xml file
COPY pom.xml .

# Copy the project source
COPY ./src ./src
COPY ./pom.xml ./pom.xml

RUN ./mvnw dependency:go-offline -B

VOLUME /tmp
VOLUME /X/attachments
COPY target/*.jar spring-boot-note-app.jar

RUN ./mvnw package -DskipTests

ENTRYPOINT ["java","-Djava.security.egd=file:/dev/./urandom","-jar","/spring-boot-note-app.jar"]
