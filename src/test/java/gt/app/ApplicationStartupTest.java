package gt.app;

import org.junit.jupiter.api.Test;

import java.net.UnknownHostException;

class ApplicationStartupTest {

    @Test
    void applicationCanBeStartedWithDefaultConfigByRunningMainMethod() throws UnknownHostException {
        /*
        this ensures that the 'Application' can be "Simply" run from IDE without doing any config change(the yml files or vm arg).
         */
        Application.main(new String[]{});
    }

}


