package gt.app.config;

import org.hibernate.jpa.boot.spi.IntegratorProvider;
import org.springframework.boot.autoconfigure.orm.jpa.HibernatePropertiesCustomizer;
import org.springframework.context.annotation.Configuration;

import java.util.List;
import java.util.Map;

@Configuration
public class HibernateConfig implements HibernatePropertiesCustomizer {
    @Override
    public void customize(Map<String, Object> hibernateProps) {
        hibernateProps.put("hibernate.integrator_provider",
            (IntegratorProvider) () -> List.of(MetadataExtractorIntegrator.INSTANCE));
    }
}
