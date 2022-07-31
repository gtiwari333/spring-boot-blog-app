package gt.app.modules.user;

import gt.app.domain.LiteUser;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.transaction.annotation.Transactional;

import java.util.Optional;

interface LiteUserRepository extends JpaRepository<LiteUser, Long> {
    @Transactional(readOnly = true)
    Optional<LiteUser> findOneByUniqueId(String uniqueId);

    @Transactional(readOnly = true)
    Optional<LiteUser> findByIdAndActiveIsTrue(Long id);
}
