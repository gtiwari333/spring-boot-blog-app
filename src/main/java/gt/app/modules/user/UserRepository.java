package gt.app.modules.user;

import gt.app.domain.User;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

interface UserRepository extends JpaRepository<User, Long> {

    @EntityGraph(attributePaths = {"authorities"})
    Optional<User> findOneWithAuthoritiesByUniqueId(String uniqueId);

    Optional<User> findOneByUniqueId(String uniqueId);

    boolean existsByUniqueId(String uniqueId);

    Optional<User> findByIdAndActiveIsTrue(Long id);

}
