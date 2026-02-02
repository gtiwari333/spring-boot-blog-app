package gt.app.modules.user;

import gt.app.domain.LiteUser;
import io.quarkus.hibernate.orm.panache.PanacheRepository;
import jakarta.enterprise.context.ApplicationScoped;
import java.util.Optional;

@ApplicationScoped
public class LiteUserRepository implements PanacheRepository<LiteUser> {

    public Optional<LiteUser> findOneByUniqueId(String uniqueId) {
        return find("uniqueId", uniqueId).firstResultOptional();
    }

    public Optional<LiteUser> findByIdAndActiveIsTrue(Long id) {
        return find("id = ?1 and active = true", id).firstResultOptional();
    }
}
