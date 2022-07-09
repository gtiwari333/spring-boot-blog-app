package gt.app.modules.user;

import gt.app.domain.AppUser;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

interface UserRepository extends JpaRepository<AppUser, Long> {

    @EntityGraph(attributePaths = {"authorities"})
    Optional<AppUser> findOneWithAuthoritiesByUniqueId(String uniqueId);

    boolean existsByUniqueId(String uniqueId);

}
