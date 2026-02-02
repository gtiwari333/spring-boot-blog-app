package gt.app.modules.user;

import gt.app.domain.AppUser;
import io.quarkus.hibernate.orm.panache.PanacheRepository;
import jakarta.enterprise.context.ApplicationScoped;
import java.util.Optional;

@ApplicationScoped
public class UserRepository implements PanacheRepository<AppUser> {

    // Equivalent to @EntityGraph: Use 'left join fetch' to load authorities in one hit
    public Optional<AppUser> findOneWithAuthoritiesByUniqueId(String uniqueId) {
        return find("from AppUser u left join fetch u.authorities where u.uniqueId = ?1", uniqueId)
            .singleResultOptional();
    }

    // Equivalent to existsByUniqueId
    public boolean existsByUniqueId(String uniqueId) {
        return count("uniqueId = ?1", uniqueId) > 0;
    }

    // Equivalent to findByIdAndActiveIsTrue
    public Optional<AppUser> findByIdAndActiveIsTrue(Long id) {
        return find("id = ?1 and active = true", id)
            .singleResultOptional();
    }
}
