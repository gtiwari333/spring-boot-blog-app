package gt.app.modules.user;

import gt.app.domain.LiteUser;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

interface LiteUserRepository extends JpaRepository<LiteUser, Long> {

    Optional<LiteUser> findOneByUniqueId(String uniqueId);

    Optional<LiteUser> findByIdAndActiveIsTrue(Long id);
}
