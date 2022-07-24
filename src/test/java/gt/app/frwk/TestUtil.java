package gt.app.frwk;

import java.net.URL;

import static java.lang.Thread.currentThread;

public class TestUtil {

    public static URL fileFromClassPath(String name) {
        URL resource = currentThread().getContextClassLoader().getResource(name);
        if (resource == null) {
            throw new IllegalArgumentException("File " + name + " not found in classpath.");
        }
        return resource;
    }


}
