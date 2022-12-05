package gt.app;

import gt.app.config.AppProperties;
import gt.app.config.Constants;
import gt.app.domain.AppUser;
import gt.app.domain.Authority;
import gt.app.domain.LiteUser;
import gt.app.domain.Note;
import gt.app.modules.note.NoteService;
import gt.app.modules.user.AuthorityService;
import gt.app.modules.user.UserService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Profile;
import org.springframework.context.event.ContextRefreshedEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;

import jakarta.persistence.EntityManager;
import java.io.File;

@Component
@Profile({Constants.SPRING_PROFILE_DEVELOPMENT, Constants.SPRING_PROFILE_TEST, Constants.SPRING_PROFILE_DOCKER})
@RequiredArgsConstructor
@Slf4j
public class DataCreator {

    final AuthorityService authorityService;
    final UserService userService;
    final NoteService noteService;

    final EntityManager entityManager;

    final AppProperties appProperties;

    @EventListener
    public void ctxRefreshed(ContextRefreshedEvent evt) {
        initData();
    }

    public void initData(){
        log.info("Context Refreshed !!, Initializing Data... ");

        new File(appProperties.fileStorage().uploadFolder() + File.separator +"attachments").mkdirs();

        Authority adminAuthority = new Authority();
        adminAuthority.setName(Constants.ROLE_ADMIN);
        authorityService.save(adminAuthority);

        Authority userAuthority = new Authority();
        userAuthority.setName(Constants.ROLE_USER);
        authorityService.save(userAuthority);

        String pwd = "$2a$10$UtqWHf0BfCr41Nsy89gj4OCiL36EbTZ8g4o/IvFN2LArruHruiRXO"; // to make it faster //value is 'pass'

        AppUser adminUser = new AppUser("system", "System", "Tiwari", "system@email");
        adminUser.setPassword(pwd);
        adminUser.setAuthorities(authorityService.findByNameIn(Constants.ROLE_ADMIN, Constants.ROLE_USER));
        userService.save(adminUser);

        AppUser user1 = new AppUser("user1", "Ganesh", "Tiwari", "gt@email");
        user1.setPassword(pwd);
        user1.setAuthorities(authorityService.findByNameIn(Constants.ROLE_USER));
        userService.save(user1);


        AppUser user2 = new AppUser("user2", "Jyoti", "Kattel", "jk@email");
        user2.setPassword(pwd);
        user2.setAuthorities(authorityService.findByNameIn(Constants.ROLE_USER));
        userService.save(user2);

        createNote(adminUser, "Admin's First Note", "Content Admin 1");
        createNote(adminUser, "Admin's Second Note", "Content Admin 2");
        createNote(user1, "User1 Note", "Content User 1");
        createNote(user2, "User2 Note", "Content User 2");


    }

    void createNote(AppUser user, String title, String content) {
        var n = new Note();
        n.setCreatedByUser(entityManager.getReference(LiteUser.class, user.getId()));
        n.setTitle(title);
        n.setContent(content);

        noteService.save(n);
    }


}
