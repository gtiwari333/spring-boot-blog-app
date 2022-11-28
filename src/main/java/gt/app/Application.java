package gt.app;

import gt.app.config.AppProperties;
import gt.app.config.Constants;
import gt.app.modules.email.dto.EmailDto;
import gt.app.modules.note.dto.NoteCreateDto;
import gt.app.modules.note.dto.NoteEditDto;
import gt.app.modules.note.dto.NoteReadDto;
import gt.app.modules.user.dto.PasswordUpdateDTO;
import gt.app.modules.user.dto.UserDTO;
import jakarta.persistence.EntityGraph;
import jakarta.persistence.NamedEntityGraph;
import lombok.extern.slf4j.Slf4j;
import org.springframework.aot.hint.MemberCategory;
import org.springframework.aot.hint.RuntimeHints;
import org.springframework.aot.hint.RuntimeHintsRegistrar;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.ImportRuntimeHints;
import org.springframework.core.env.Environment;
import org.springframework.transaction.annotation.EnableTransactionManagement;

import java.net.InetAddress;
import java.net.UnknownHostException;
import java.util.Arrays;
import java.util.Map;

@SpringBootApplication
@Slf4j
@EnableConfigurationProperties(AppProperties.class)
@EnableTransactionManagement(proxyTargetClass = true)
@ImportRuntimeHints(MyRuntimeHints.class)
public class Application {

    public static void main(String[] args) throws UnknownHostException {

        var app = new SpringApplication(Application.class);
        app.setDefaultProperties(Map.of("spring.profiles.default", Constants.SPRING_PROFILE_DEVELOPMENT));
        Environment env = app.run(args).getEnvironment();

        log.info("""
                Access URLs:
                ----------------------------------------------------------
                \tLocal: \t\t\thttp://localhost:{}
                \tExternal: \t\thttp://{}:{}
                \tEnvironment: \t{}\s
                \t----------------------------------------------------------""",
            env.getProperty("server.port"),
            InetAddress.getLocalHost().getHostAddress(),
            env.getProperty("server.port"),
            Arrays.toString(env.getActiveProfiles())
        );
    }

}

//until https://github.com/spring-projects/spring-data-jpa/issues/2681 gets released/

/**
 * currently getting this error https://github.com/spring-projects-experimental/spring-native/issues/1728
 * Caused by: java.lang.IllegalArgumentException: The EntityGraph-Feature requires at least a JPA 2.1 persistence provider
 *         at org.springframework.util.Assert.isTrue(Assert.java:121) ~[na:na]
 *         at org.springframework.data.jpa.repository.query.Jpa21Utils.tryGetFetchGraph(Jpa21Utils.java:103) ~[na:na]
 *         at org.springframework.data.jpa.repository.query.Jpa21Utils.getFetchGraphHint(Jpa21Utils.java:76) ~[na:na]
 *         at org.springframework.data.jpa.repository.query.AbstractJpaQuery.applyEntityGraphConfiguration(AbstractJpaQuery.java:250) ~[note-app:3.0.0-RC1]
 *         at org.springframework.data.jpa.repository.query.AbstractJpaQuery.createQuery(AbstractJpaQuery.java:234) ~[note-app:3.0.0-RC1]
 *         at org.springframework.data.jpa.repository.query.JpaQueryExecution$SingleEntityExecution.doExecute(JpaQueryExecution.java:193) ~[na:na]
 *         at org.springframework.data.jpa.repository.query.JpaQueryExecution.execute(JpaQueryExecution.java:90) ~[note-app:3.0.0-RC1]
 *         at org.springframework.data.jpa.repository.query.AbstractJpaQuery.doExecute(AbstractJpaQuery.java:148) ~[note-app:3.0.0-RC1]
 *         at org.springframework.data.jpa.repository.query.AbstractJpaQuery.execute(AbstractJpaQuery.java:136) ~[note-app:3.0.0-RC1]
 *         at org.springframework.data.repository.core.support.RepositoryMethodInvoker.doInvoke(RepositoryMethodInvoker.java:137) ~[note-app:3.0.0-RC1]
 */
class MyRuntimeHints implements RuntimeHintsRegistrar {
    @Override
    public void registerHints(RuntimeHints hints, ClassLoader classLoader) {
        hints.reflection().registerType(NamedEntityGraph.class,
            hint -> hint.onReachableType(EntityGraph.class).withMembers(MemberCategory.INVOKE_PUBLIC_METHODS));

        hints
            .reflection()
            .registerType(AppProperties.class, MemberCategory.values())
            .registerType(AppProperties.FileStorage.class, MemberCategory.values())
            .registerType(EmailDto.class, MemberCategory.values())
            .registerType(EmailDto.FileBArray.class, MemberCategory.values())
            .registerType(PasswordUpdateDTO.class, MemberCategory.values())
            .registerType(UserDTO.class, MemberCategory.values())
            .registerType(NoteCreateDto.class, MemberCategory.values())
            .registerType(NoteEditDto.class, MemberCategory.values())
            .registerType(NoteReadDto.class, MemberCategory.values())
            .registerType(NoteReadDto.FileInfo.class, MemberCategory.values());
    }
}
