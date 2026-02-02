package gt.app.modules.user;

import gt.app.domain.Authority;
import io.quarkus.hibernate.orm.panache.PanacheRepositoryBase;
import jakarta.enterprise.context.ApplicationScoped;

import java.util.Collection;
import java.util.Set;
import java.util.stream.Collectors;

@ApplicationScoped
class AuthorityRepository implements PanacheRepositoryBase<Authority, String> {

    /**
     * Equivalent to findByNameIn
     * Panache automatically handles Collections in 'IN' clauses.
     */
    public Set<Authority> findByNameIn(Collection<String> names) {
        return find("name in ?1", names)
            .stream()
            .collect(Collectors.toSet());
    }
}
