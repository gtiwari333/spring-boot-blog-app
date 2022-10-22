package gt.app.config;

import gt.app.config.security.SecurityUtils;
import gt.app.domain.LiteUser;
import jakarta.persistence.PersistenceContext;
import org.springframework.data.domain.AuditorAware;
import org.springframework.stereotype.Component;

import jakarta.persistence.EntityManager;
import java.util.Optional;

@Component
public class AuditorResolver implements AuditorAware<LiteUser> {

    //https://github.com/spring-projects-experimental/spring-native/issues/1597
    @PersistenceContext private EntityManager entityManager;

    @Override
    public Optional<LiteUser> getCurrentAuditor() {

        Long userId = SecurityUtils.getCurrentUserId();
        if (userId == null) {
            return Optional.empty();
        }

        return Optional.ofNullable(entityManager.getReference(LiteUser.class, userId));
    }
}
