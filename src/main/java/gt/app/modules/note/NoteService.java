package gt.app.modules.note;

import gt.app.domain.Note;
import gt.app.domain.ReceivedFile;
import gt.app.modules.file.FileService;
import gt.app.modules.note.dto.*;
import io.quarkus.panache.common.Page;
import io.vertx.ext.web.FileUpload;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.stream.Collectors;

@ApplicationScoped
@RequiredArgsConstructor
public class NoteService {

    private static final ReceivedFile.FileGroup FILE_GROUP = ReceivedFile.FileGroup.NOTE_ATTACHMENT;
    private final NoteRepository noteRepository;
    private final FileService fileService;
    private final NoteMapper noteMapper;

    @Transactional
    public Note createNote(NoteCreateDto dto) {
        List<ReceivedFile> files = new ArrayList<>();

        // Note: Change NoteCreateDto to use List<FileUpload> for Quarkus
        for (FileUpload mpf : dto.files()) {
            if (mpf.size() == 0) {
                continue;
            }

            String fileId = fileService.store(FILE_GROUP, mpf);
            files.add(new ReceivedFile(FILE_GROUP, mpf.fileName(), fileId));
        }

        Note note = noteMapper.createToEntity(dto);
        note.getAttachedFiles().addAll(files);

        return save(note);
    }

    @Transactional
    public Note update(NoteEditDto dto) {
        return noteRepository.findByIdOptional(dto.id())
            .map(note -> {
                noteMapper.createToEntity(dto, note);
                return save(note);
            }).orElseThrow();
    }

    public NoteReadDto read(Long id) {
        return noteRepository.findByIdOptional(id)
            .map(noteMapper::mapForRead).orElseThrow();
    }

    @Transactional
    public Note save(Note note) {
        noteRepository.persist(note);
        return note;
    }

    public List<NoteReadDto> readAll(Page page) {
        return noteRepository.findAll().page(page).list()
            .stream()
            .map(noteMapper::mapForRead)
            .collect(Collectors.toList());
    }

    public List<NoteReadDto> readAllByUser(Page page, Long userId) {
        // Using the custom repository method we converted earlier
        return noteRepository.findByUserWithDetails(userId, page)
            .stream()
            .map(noteMapper::mapForRead)
            .collect(Collectors.toList());
    }

    @Transactional
    public void delete(Long id) {
        noteRepository.deleteById(id);
    }

    public Long findCreatedByUserIdById(Long id) {
        return noteRepository.findCreatedByUserIdById(id);
    }
}
