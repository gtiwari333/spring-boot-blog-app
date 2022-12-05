package gt.app.config;

import gt.app.config.security.SecurityUtils;
import gt.app.domain.LiteUser;
import jakarta.persistence.EntityManager;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.AuditorAware;
import org.springframework.stereotype.Component;

import java.util.Optional;

@Component
@RequiredArgsConstructor
public class AuditorResolver implements AuditorAware<LiteUser> {

    private final EntityManager entityManager;

    @Override
    public Optional<LiteUser> getCurrentAuditor() {

        Long userId = SecurityUtils.getCurrentUserId();
        if (userId == null) {
            return Optional.empty();
        }

        return Optional.ofNullable(entityManager.getReference(LiteUser.class, userId));
    }
}
