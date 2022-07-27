package gt.app.modules.user;

import gt.app.domain.AppUser;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.transaction.annotation.Transactional;

import java.util.Optional;

interface UserRepository extends JpaRepository<AppUser, Long> {

    @EntityGraph(attributePaths = {"authorities"})
    @Transactional(readOnly = true)
    Optional<AppUser> findOneWithAuthoritiesByUniqueId(String uniqueId);

    @Transactional(readOnly = true)
    boolean existsByUniqueId(String uniqueId);

}
