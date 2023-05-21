package gt.app.modules.note;

import gt.app.domain.Note;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.transaction.annotation.Transactional;

import java.util.Optional;

interface NoteRepository extends JpaRepository<Note, Long> {

    @EntityGraph(attributePaths = {"createdByUser"})
    @Transactional(readOnly = true)
    Optional<Note> findById(Long id);

    @EntityGraph(attributePaths = {"createdByUser"})
    @Transactional(readOnly = true)
    Page<Note> findAll(Pageable pageable);

    @EntityGraph(attributePaths = {"createdByUser"})
    @Transactional(readOnly = true)
    Page<Note> findByCreatedByUserIdOrderByCreatedDateDesc(Pageable pageable, Long userId);

    @Query("select n.createdByUser.id from Note n where n.id=:id ")
    @Transactional(readOnly = true)
    Long findCreatedByUserIdById(@Param("id") Long id);
}
