package gt.app.modules.note;

import gt.app.domain.Note;
import io.quarkus.hibernate.orm.panache.PanacheRepository;
import io.quarkus.panache.common.Page;
import io.quarkus.panache.common.Sort;
import jakarta.enterprise.context.ApplicationScoped;
import java.util.List;
import java.util.Optional;

@ApplicationScoped
public class NoteRepository implements PanacheRepository<Note> {

    // Equivalent to @EntityGraph: Use HQL 'fetch' to join associations
    public Optional<Note> findByIdWithDetails(Long id) {
        return find("from Note n left join fetch n.createdByUser left join fetch n.attachedFiles where n.id = ?1", id)
            .singleResultOptional();
    }

    // findAll with pagination and fetching
    public List<Note> findAllWithDetails(Page page) {
        return find("from Note n left join fetch n.createdByUser left join fetch n.attachedFiles")
            .page(page)
            .list();
    }

    // findByCreatedByUserIdOrderByCreatedDateDesc equivalent
    public List<Note> findByUserWithDetails(Long userId, Page page) {
        return find("from Note n left join fetch n.createdByUser left join fetch n.attachedFiles " +
                "where n.createdByUser.id = ?1",
            Sort.by("createdDate").descending(),
            userId)
            .page(page)
            .list();
    }

    // Custom projection query
    public Long findCreatedByUserIdById(Long id) {
        return find("select n.createdByUser.id from Note n where n.id = ?1", id)
            .project(Long.class)
            .singleResult();
    }
}
