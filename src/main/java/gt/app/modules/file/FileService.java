package gt.app.modules.file;

import gt.app.config.AppProperties;
import gt.app.domain.ReceivedFile;
import io.vertx.ext.web.FileUpload;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import jakarta.validation.constraints.NotNull;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.UUID;

@ApplicationScoped
public class FileService {

    private final Path rootLocation;

    @Inject
    public FileService(AppProperties appProperties) {
        this.rootLocation = Path.of(appProperties.fileStorage().uploadFolder());
    }

    public String store(ReceivedFile.FileGroup fileGroup, @NotNull FileUpload file) {
        try {
            String fileIdentifier = getCleanedFileName(file.uploadedFileName());
            Path targetPath = getStoredFilePath(fileGroup, fileIdentifier);

            // Ensure directories exist
            Files.createDirectories(targetPath.getParent());

            // FileUpload stores data in a temp file; move it to the target
            Files.move(Path.of(fileIdentifier), targetPath, StandardCopyOption.REPLACE_EXISTING);

            return fileIdentifier;
        } catch (IOException e) {
            throw new RuntimeException("Failed to store file " + file.fileName(), e);
        }
    }

    public java.io.File loadAsFile(ReceivedFile.FileGroup fileGroup, String fileIdentifier) {
        try {
            Path targetPath = getStoredFilePath(fileGroup, fileIdentifier);
            java.io.File file = targetPath.toFile();

            if (file.exists() && file.canRead()) {
                return file;
            } else {
                throw new IOException("Could not read file: " + targetPath);
            }
        } catch (IOException e) {
            throw new RetrievalException("Could not read file: " + fileIdentifier + " , group " + fileGroup, e);
        }
    }

    private String getCleanedFileName(String originalName) throws IOException {
        if (originalName == null || originalName.isEmpty()) {
            throw new IOException("Failed to store empty file " + originalName);
        }

        if (originalName.contains("..")) {
            // This is a security check
            throw new IOException("Cannot store file with relative path outside current directory " + originalName);
        }

        return UUID.randomUUID().toString();
    }

    private String getSubFolder(ReceivedFile.FileGroup fileGroup) throws IOException {
        if (fileGroup == ReceivedFile.FileGroup.NOTE_ATTACHMENT) {
            return "attachments";
        }

        throw new IOException("File group subfolder " + fileGroup + " is not implemented");
    }

    private Path getStoredFilePath(ReceivedFile.FileGroup fileGroup, String fileIdentifier) throws IOException {
        return rootLocation.resolve(getSubFolder(fileGroup)).resolve(fileIdentifier);
    }
}
