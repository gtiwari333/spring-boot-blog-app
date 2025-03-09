package gt.app.modules.user;

import gt.app.domain.Authority;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Collection;
import java.util.Set;

interface AuthorityRepository extends JpaRepository<Authority, String> {
    Set<Authority> findByNameIn(Collection<String> name);
}
