package gt.app.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.data.jpa.repository.config.EnableJpaAuditing;

@EnableJpaAuditing //now @CreatedBy, @LastModifiedBy works
@Configuration(proxyBeanMethods = false)
public class JpaConfig {
}
