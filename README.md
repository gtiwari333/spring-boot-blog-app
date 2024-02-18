# A BlogApp with Spring Boot

#### More complex version is here: https://github.com/gtiwari333/spring-boot-web-application-seed

### Intro

This is a simple micro blogging application where you can post a note/blog with attachments and other can view it.

The default username/passwords are listed on : gt.app.Application.initData, which are:

- system/pass
- user1/pass
- user2/pass

### Requirements

- JDK 21+
- Lombok configured on IDE
    - http://ganeshtiwaridotcomdotnp.blogspot.com/2016/03/configuring-lombok-on-intellij.html
    - For eclipse, download the lombok jar, run it, and point to eclipse installation
- Maven (optional)
- Docker

### How to Run

- Clone/Download and Import project into your IDE, compile and run Application.java
- Update run configuration to run maven goal `wro4j:run` Before Launch. It should be after 'Build'
  OR

- ./mvnw compile spring-boot:run //if you don't have maven installed in your PC

OR

- ./mvnw compile spring-boot:run //if you have maven installed in your PC

And open   `http://localhost:8080` on your browser

Optionally, you can start the docker containers yourself using:

`docker-compose --profile mailHog up` to start just the mailHog container(required by default 'dev' profile)

Or

`docker-compose --profile all up` to start both mailHog and mysql (if you want to use 'docker' or 'prod' profile)

`sudo chmod 666 /var/run/docker.sock` to fix following error
``` 
org.springframework.boot.docker.compose.core.ProcessExitException: 'docker version --format {{.Client.Version}}' failed with exit code 1.

Stdout:
20.10.24


Stderr:
Got permission denied while trying to connect to the Docker daemon socket at unix:///var/run/docker.sock: 
    Get "http://%2Fvar%2Frun%2Fdocker.sock/v1.24/version": dial unix /var/run/docker.sock: connect: permission denied
```

## Run Tests

##### Running full tests

`./mvnw clean verify`

##### Running unit tests only (it uses maven surefire plugin)

`./mvnw  compiler:testCompile resources:testResources  surefire:test`

##### Running integration tests only (it uses maven-failsafe-plugin)

`./mvnw  compiler:testCompile resources:testResources  failsafe:integration-test`

## Code Quality

##### The `error-prone` runs at compile time.

##### The `modernizer` `checkstyle` and `spotbugs` plugin are run as part of maven `test-compile` lifecycle phase. use `mvn spotbugs:gui' to

##### SonarQube scan

Run sonarqube server using docker
`docker run -e SONAR_ES_BOOTSTRAP_CHECKS_DISABLE=true -p 9000:9000 sonarqube:latest`

Perform scan:
`./mvnw sonar:sonar`
./mvnw sonar:sonar -Dsonar.login=admin -Dsonar.password=admin

View Reports in SonarQube web ui:

- visit http://localhost:9000
- default login and password are `admin`, you will be asked to change password after logging in with default
  username/password
- (optional) change sonarqube admin password without logging
  in: `curl -u admin:admin -X POST "http://localhost:9000/api/users/change_password?login=admin&previousPassword=admin&password=NEW_PASSWORD"`
- if you change the password, make sure the update `-Dsonar.password=admin` when you run sonarqube next time

### Dependency vulnerability scan

Owasp dependency check plugin is configured. Run `./mvnw dependency-check:check` to run scan and
open `dependency-check-report.html` from target to see the report.

### Dependency/plugin version checker

    ./mvnw versions:display-dependency-updates
    ./mvnw versions:display-plugin-updates

### Included Features/Samples
- GraalVM native image generation
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
- H2 db for local, Console enabled for local ( http://localhost:8080/h2-console/, db url: jdbc:h2:mem:testdb, username:sa)
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

    `./mvnw versions:display-dependency-updates`
    `./mvnw versions:display-plugin-updates`

## Create docker image using buildpack

    ./mvnw spring-boot:build-image

    docker run --rm -p 8080:8080 docker.io/library/note-app:3.2.1


## Generate native executable:
- Required: GraalVM 22.3+ (for Spring Boot 3) 
- Install using sdkman 
- https://docs.spring.io/spring-boot/docs/current/reference/html/native-image.html#native-image.developing-your-first-application.native-build-tools.prerequisites
    `sdk install java  22.3.r17-nik`
    `sdk use java  22.3.r17-nik`

- Create native executable `./mvnw native:compile -Pnative,dev`
- Run it   `./target/note-app`

OR

- Generate docker image with native executable `./mvnw spring-boot:build-image -Pnative,dev`
- Run it `docker run --rm -p 8080:8080 docker.io/library/note-app:3.2.1`


## Native Test:
- Run with `./mvnw test -PnativeTest`
- Spring Boot 3.0.0: native-test is not working due to spock ( and possibly other dependencies too) 



# Results after enabling virtual thread

ab -k -c 10 -n 2000 http://localhost:8080/



Before 
```
Connection Times (ms)
              min  mean[+/-sd] median   max
Connect:        0    0   0.1      0       1
Processing:     3    4   0.9      4       9
Waiting:        3    4   0.8      4       8
Total:          3    4   0.9      4       9

Percentage of the requests served within a certain time (ms)
  50%      4
  66%      4
  75%      5
  80%      5
  90%      5
  95%      6
  98%      7
  99%      8
 100%      9 (longest request)

```


After
``` 
Connection Times (ms)
              min  mean[+/-sd] median   max
Connect:        0    0   0.1      0       1
Processing:     3    4   0.7      4       9
Waiting:        3    4   0.7      4       8
Total:          3    5   0.7      4       9
WARNING: The median and mean for the total time are not within a normal deviation
        These results are probably not that reliable.

Percentage of the requests served within a certain time (ms)
  50%      4
  66%      5
  75%      5
  80%      5
  90%      5
  95%      6
  98%      6
  99%      7
 100%      9 (longest request)

```


After introducing a delay to simulate slow blocking API and thousand concurrent requests. Its similar for less concurrent request. Virtual thread outperforms when we have too many concurrent requests.


ab  -c 1000 -n 15000 http://localhost:8080/

```java
public class IndexController {

    @GetMapping({"/", ""})
    public String index(Model model, Pageable pageable) throws InterruptedException {
        Thread.sleep(1500);
        ...
    }
```

before

``` 
Connection Times (ms)
              min  mean[+/-sd] median   max
Connect:        0   19 132.4      0    1030
Processing:  1529 7341 918.6   7547    7631
Waiting:     1528 7340 918.7   7547    7630
Total:       1555 7359 905.6   7548    7817

Percentage of the requests served within a certain time (ms)
  50%   7548
  66%   7552
  75%   7556
  80%   7558
  90%   7570
  95%   7585
  98%   7611
  99%   7628
 100%   7817 (longest request)

```

after

AMAZING  !!!


``` 

Connection Times (ms)
              min  mean[+/-sd] median   max
Connect:        0    1   4.7      0      23
Processing:  1503 1526  60.8   1507    1919
Waiting:     1503 1526  60.8   1506    1918
Total:       1503 1528  64.4   1507    1940

Percentage of the requests served within a certain time (ms)
  50%   1507
  66%   1510
  75%   1514
  80%   1519
  90%   1559
  95%   1664
  98%   1804
  99%   1867
 100%   1940 (longest request)


```
 
