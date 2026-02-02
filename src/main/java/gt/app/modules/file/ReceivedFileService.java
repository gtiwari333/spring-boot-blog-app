package gt.app.modules.file;

import gt.app.domain.ReceivedFile;
import jakarta.enterprise.context.ApplicationScoped;
import lombok.RequiredArgsConstructor;

import java.util.Optional;
import java.util.UUID;

@ApplicationScoped
@RequiredArgsConstructor
public class ReceivedFileService {

    final ReceivedFileRepository receivedFileRepository;

    public  ReceivedFile findById(UUID id) {
        return receivedFileRepository.findById(id);
    }
}
