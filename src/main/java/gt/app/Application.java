package gt.app;

import gt.app.config.AppProperties;
import gt.app.config.Constants;
import gt.app.modules.user.AppUserDetailsService;
import gt.app.modules.user.UserAuthorityService;
import lombok.extern.slf4j.Slf4j;
import org.hibernate.tuple.CreationTimestampGeneration;
import org.hibernate.tuple.GeneratedValueGeneration;
import org.hibernate.tuple.UpdateTimestampGeneration;
import org.hibernate.type.EnumType;
import org.springframework.aop.SpringProxy;
import org.springframework.aop.framework.Advised;
import org.springframework.beans.factory.aspectj.AnnotationBeanConfigurerAspect;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.core.DecoratingProxy;
import org.springframework.core.env.Environment;
import org.springframework.data.jpa.domain.support.AuditingBeanFactoryPostProcessor;
import org.springframework.nativex.hint.ProxyHint;
import org.springframework.nativex.hint.ProxyHints;
import org.springframework.nativex.hint.TypeHint;
import org.springframework.nativex.hint.TypeHints;
import org.springframework.transaction.annotation.EnableTransactionManagement;

import java.net.InetAddress;
import java.net.UnknownHostException;
import java.util.Arrays;
import java.util.Map;

@SpringBootApplication
@Slf4j
@EnableConfigurationProperties(AppProperties.class)
@EnableTransactionManagement(proxyTargetClass = true)
@TypeHints({
    @TypeHint(types = AnnotationBeanConfigurerAspect.class),
    @TypeHint(types = AuditingBeanFactoryPostProcessor.class),
    @TypeHint(types = CreationTimestampGeneration.class),
    @TypeHint(types = UpdateTimestampGeneration.class),
    @TypeHint(types = GeneratedValueGeneration.class),
    @TypeHint(types = EnumType.class),
})
@ProxyHints({
    @ProxyHint(types = {UserAuthorityService.class, SpringProxy.class, Advised.class, DecoratingProxy.class}),
    @ProxyHint(types = {AppUserDetailsService.class, SpringProxy.class, Advised.class, DecoratingProxy.class})
})
public class Application {

    public static void main(String[] args) throws UnknownHostException {

        SpringApplication app = new SpringApplication(Application.class);
        app.setDefaultProperties(Map.of("spring.profiles.default", Constants.SPRING_PROFILE_DEVELOPMENT));
        Environment env = app.run(args).getEnvironment();

        log.info("Access URLs:\n----------------------------------------------------------\n\t" +
                "Local: \t\t\thttp://localhost:{}\n\t" +
                "External: \t\thttp://{}:{}\n\t" +
                "Environment: \t{} \n\t" +
                "----------------------------------------------------------",
            env.getProperty("server.port"),
            InetAddress.getLocalHost().getHostAddress(),
            env.getProperty("server.port"),
            Arrays.toString(env.getActiveProfiles())
        );
    }

}
