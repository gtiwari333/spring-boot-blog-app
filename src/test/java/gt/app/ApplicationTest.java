package gt.app;

import gt.app.config.Constants;
import lombok.extern.slf4j.Slf4j;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Profile;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ActiveProfiles;

import static org.junit.jupiter.api.Assertions.assertTrue;

@SpringBootTest
@Slf4j
@DirtiesContext
@ActiveProfiles(Constants.SPRING_PROFILE_TEST)
class ApplicationTest {

    @Test
    void contextLoads() {
        assertTrue(true, "Context loads !!!");
    }

}


