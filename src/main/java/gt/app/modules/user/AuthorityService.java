package gt.app.modules.user;

import gt.app.domain.Authority;
import jakarta.enterprise.context.ApplicationScoped;
import lombok.RequiredArgsConstructor;

import java.util.List;
import java.util.Set;

@ApplicationScoped
@RequiredArgsConstructor
public class AuthorityService {

    final  AuthorityRepository authorityRepository;

    public void save(Authority auth) {
        authorityRepository.persist(auth);
    }

    public Set<Authority> findByNameIn(String... roles) {
        return authorityRepository.findByNameIn(List.of(roles));
    }
}
