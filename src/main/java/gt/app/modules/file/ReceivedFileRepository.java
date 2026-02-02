package gt.app.modules.file;

import gt.app.domain.ReceivedFile;
import io.quarkus.hibernate.orm.panache.PanacheRepositoryBase;
import jakarta.enterprise.context.ApplicationScoped;

import java.util.UUID;

@ApplicationScoped
public class ReceivedFileRepository implements PanacheRepositoryBase<ReceivedFile, UUID> {
}
