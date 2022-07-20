# A BlogApp with Spring Boot

#### More complex version is here: https://github.com/gtiwari333/spring-boot-web-application-seed

### Intro

This is a simple micro blogging application where you can post a note/blog with attachments and other can view it.

The default username/passwords are listed on : gt.app.Application.initData, which are:

- system/pass
- user1/pass
- user2/pass

### Requirements

- JDK 17+
- Lombok configured on IDE
    - http://ganeshtiwaridotcomdotnp.blogspot.com/2016/03/configuring-lombok-on-intellij.html
    - For eclipse, download the lombok jar, run it, and point to eclipse installation
- Maven (optional)

### How to Run

- Clone/Download and Import project into your IDE, compile and run Application.java
- Update run configuration to run maven goal `wro4j:run` Before Launch. It should be after 'Build'
  OR

- mvnw compile spring-boot:run //if you don't have maven installed in your PC

OR

- mvnw compile spring-boot:run //if you have maven installed in your PC

And open   `http://localhost:8080` on your browser

## Run Tests

##### Running full tests

`mvnw clean test`

##### Running unit tests only (it uses maven surefire plugin)

`mvnw  compiler:testCompile resources:testResources  surefire:test`

##### Running integration tests only (it uses maven-failsafe-plugin)

`mvnw  compiler:testCompile resources:testResources  failsafe:integration-test`

## Code Quality

##### The `error-prone` runs at compile time.
##### The `modernizer` `checkstyle` and `spotbugs` plugin are run as part of maven `test-compile` lifecycle phase.

##### SonarQube scan

Run sonarqube server using docker
`docker run -e SONAR_ES_BOOTSTRAP_CHECKS_DISABLE=true -p 9000:9000 sonarqube:latest`

Perform scan:
`mvnw sonar:sonar`
mvnw sonar:sonar -Dsonar.login=admin -Dsonar.password=admin

View Reports in SonarQube web ui:

- visit http://localhost:9000
- default login and password are `admin`, you will be asked to change password after logging in with default
  username/password
- (optional) change sonarqube admin password without logging
  in: `curl -u admin:admin -X POST "http://localhost:9000/api/users/change_password?login=admin&previousPassword=admin&password=NEW_PASSWORD"`
- if you change the password, make sure the update `-Dsonar.password=admin` when you run sonarqube next time

### Included Features/Samples
- Modular application
- Data JPA with User/Authority/Note/ReceivedFile entities, example of EntityGraph
- Default test data created while running the app
- Public and internal pages
- MVC with thymeleaf templating
- File upload/download
- Live update of thymeleaf templates for local development
- HTML fragments
- webjar - bootstrap4 + jquery
- Custom Error page
- Request logger filter
- Swagger API Docs with UI  ( http://localhost:8080/swagger-ui.html)
- @RestControllerAdvice, @ControllerAdvice demo
- CRUD Note + File upload
- Spring / Maven profiles for dev/prod ...
- Dockerfile to run images
- Docker maven plugin to publish images (follow docker-steps.md)
- Deploy to Amazon EC2 ( follow docker-steps.md )
- Code Generation: lombok, mapstruct
- H2 db for local, Console enabled for local ( http://localhost:8080/h2-console/, db url: jdbc:h2:mem:testdb, username:
  sa)
- MySQL or any other SQL db can be configured for prod/docker etc profiles
- User/User_Authority entity and repository/services
    - login, logout, home pages based on user role
- Security with basic config
- Domain object Access security check on update/delete using custom PermissionEvaluator
- public home page -- view all notes by all
- private pages based on user roles
- Test cases - unit/integration with JUnit 5, Mockito and Spring Test
- Tests with Spock Framework (Groovy 3, Spock 2)
- e2e with Selenide, fixtures. default data generated using Spring
- Architecture test using ArchUnit
- Email
- Account management/Signup UI

Future: do more stuff

- background jobs with Quartz
- Liquibase/Flyway change log
- Integrate Markdown editor for writing notes

### Dependency/plugin version checker

    mvnw versions:display-dependency-updates
    mvnw versions:display-plugin-updates


