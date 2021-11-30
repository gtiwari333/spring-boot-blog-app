package gt.app;

import gt.app.config.Constants;
import gt.app.domain.Note;
import gt.app.domain.User;
import gt.app.exception.InvalidDataException;
import lombok.extern.slf4j.Slf4j;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;

import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest
@Slf4j
@ActiveProfiles(Constants.SPRING_PROFILE_TEST)
class ApplicationTest {

    public Note newNote = new Note();
    public User user = new User();
    public User objectUser;

    @BeforeEach
    public void setup() {
        objectUser = new User("99" , "Ion", "Baton", "ion.baton@mail.ru");
    }

    @Test
    void contextLoads() {
        assertTrue(true, "Context loads !!!");
    }

    @Test
    @DisplayName("Test Constructor!")
    public void creatingNewUser()
    {
        newNote.setTitle("LABORATOR SOMIPP");
        newNote.setContent("JENKINS PIPELINE");
        Assertions.assertEquals("LABORATOR SOMIPP", newNote.getTitle());
        Assertions.assertEquals("JENKINS PIPELINE", newNote.getContent());
    }

    @Test
    @DisplayName("Test Invalid Email Exception!")
    public void invalidEmail()
    {
        String email = "ion.baton#mail.ru";
        InvalidDataException thrown = assertThrows(InvalidDataException.class,
        () -> user.setEmail(email),"InvalidDataException error was expected");

        assertEquals("Email value not recognized (" + email + ")", thrown.getMessage());
    }

    @Test
    @DisplayName("Test values from object!")
    public void gettingData()
    {
        Assertions.assertEquals("Baton",objectUser.getLastName());
        Assertions.assertEquals("Ion",objectUser.getFirstName());
        Assertions.assertEquals("ion.baton@mail.ru",objectUser.getEmail());
    }

}


