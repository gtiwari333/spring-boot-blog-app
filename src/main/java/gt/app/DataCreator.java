package gt.app;

import gt.app.config.AppProperties;
import gt.app.config.Constants;
import gt.app.domain.*;
import gt.app.modules.note.NoteService;
import gt.app.modules.user.AuthorityService;
import gt.app.modules.user.UserService;
import jakarta.persistence.EntityManager;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.annotation.Profile;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.io.File;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.stream.Stream;

@Component
@Profile({Constants.SPRING_PROFILE_DEVELOPMENT, Constants.SPRING_PROFILE_TEST, Constants.SPRING_PROFILE_DOCKER})
@RequiredArgsConstructor
@Slf4j
public class DataCreator {

    private static final int BATCH_SIZE = 100;

    final AuthorityService authorityService;
    final UserService userService;
    final NoteService noteService;

    final EntityManager entityManager;

    final AppProperties appProperties;

    @EventListener
    @Transactional
    public void ctxRefreshed(ApplicationReadyEvent evt) {
        initData();
    }

    public void initData() {
        log.info("Context Refreshed !!, Initializing Data... ");

        File uploadFolder = Path.of(appProperties.fileStorage().uploadFolder()).toFile();
        if (!uploadFolder.exists()) {
            if (uploadFolder.mkdirs() && Stream.of(ReceivedFile.FileGroup.values()).allMatch(f -> Path.of(uploadFolder.getAbsolutePath()).toFile().mkdir())) {
                log.info("Upload folder created successfully");
            } else {
                log.info("Failure to create upload folder");
            }
        }

        if (userService.existsByUniqueId("system")) {
            log.info("DB already initialized !!!");
            return;
        }
        Authority adminAuthority = new Authority();
        adminAuthority.setName(Constants.ROLE_ADMIN);
        entityManager.persist(adminAuthority);

        Authority userAuthority = new Authority();
        userAuthority.setName(Constants.ROLE_USER);
        entityManager.persist(userAuthority);

        String pwd = "$2a$10$UtqWHf0BfCr41Nsy89gj4OCiL36EbTZ8g4o/IvFN2LArruHruiRXO"; // pre-hashed 'pass'

        AppUser adminUser = new AppUser("system", "System", "Tiwari", "system@email");
        adminUser.setPassword(pwd);
        adminUser.setAuthorities(authorityService.findByNameIn(Constants.ROLE_ADMIN, Constants.ROLE_USER));
        entityManager.persist(adminUser);

        List<AppUser> users = new ArrayList<>();
        for (int i = 1; i <= 50; i++) {
            AppUser user = new AppUser("user" + i, "FirstName" + i, "LastName" + i, "user" + i + "@email");
            user.setPassword(pwd);
            user.setAuthorities(authorityService.findByNameIn(Constants.ROLE_USER));
            entityManager.persist(user);
            users.add(user);
        }
        // Flush users so getReference() works for note creation
        entityManager.flush();

        entityManager.persist(createNote(adminUser, "Admin's First Note", "Content Admin 1"));
        entityManager.persist(createNote(adminUser, "Admin's Second Note", "Content Admin 2"));

        // Batch-insert 15,000 notes with periodic flush/clear to avoid memory bloat
        long start = System.currentTimeMillis();
        for (int i = 1; i <= 15000; i++) {
            AppUser user = users.get(i % users.size());
            entityManager.persist(createNote(user, "Note Title " + i, "Content for note number " + i));
            if (i % BATCH_SIZE == 0) {
                entityManager.flush();
                entityManager.clear();
            }
        }
        entityManager.flush();
        long elapsed = System.currentTimeMillis() - start;
        log.info("Seeded 15,000 notes in {}ms (batch size: {})", elapsed, BATCH_SIZE);
    }

    private Note createNote(AppUser user, String title, String content) {
        var n = new Note();
        n.setCreatedByUser(entityManager.getReference(LiteUser.class, user.getId()));
        n.setTitle(title);
        n.setContent(content);
        return n;
    }


}
