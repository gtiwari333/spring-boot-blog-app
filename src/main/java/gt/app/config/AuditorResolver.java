package gt.app.config;

import gt.app.config.security.SecurityUtils;
import gt.app.domain.AppUser;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.AuditorAware;
import org.springframework.stereotype.Component;

import javax.persistence.EntityManager;
import java.util.Optional;

@Component
@RequiredArgsConstructor
public class AuditorResolver implements AuditorAware<AppUser> {

    private final EntityManager entityManager;

    @Override
    public Optional<AppUser> getCurrentAuditor() {

        Long userId = SecurityUtils.getCurrentUserId();
        if (userId == null) {
            return Optional.empty();
        }

        return Optional.ofNullable(entityManager.getReference(AppUser.class, userId));
    }
}
