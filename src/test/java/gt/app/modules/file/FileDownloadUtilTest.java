package gt.app.modules.file;

import gt.app.frwk.TestUtil;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.util.MimeTypeUtils;

import java.io.IOException;
import java.net.URL;

import static org.assertj.core.api.Assertions.assertThat;

class FileDownloadUtilTest {

    @Test
    void downloadFile() throws IOException {

        URL toDownload = TestUtil.fileFromClassPath("blob/test.txt");

        MockHttpServletResponse resp = new MockHttpServletResponse();

        FileDownloadUtil.downloadFile(resp, toDownload, "original.txt");


        assertThat(resp.getHeader("Content-Disposition")).isEqualTo("attachment; filename=original.txt");
        assertThat(resp.getContentType()).isEqualTo(MimeTypeUtils.APPLICATION_OCTET_STREAM.getType());

        assertThat(resp.getContentAsString()).contains("Some Content");
        assertThat(resp.getContentAsString()).contains("Content at the end");

    }


    @Test
    void downloadFileWithContentType() throws IOException {

        URL toDownload = TestUtil.fileFromClassPath("blob/test.txt");

        MockHttpServletResponse resp = new MockHttpServletResponse();

        FileDownloadUtil.downloadFile(resp, toDownload, "original.txt", "mimetype");


        assertThat(resp.getHeader("Content-Disposition")).isEqualTo("attachment; filename=original.txt");
        assertThat(resp.getContentType()).isEqualTo("mimetype");

        assertThat(resp.getContentAsString()).contains("Some Content");
        assertThat(resp.getContentAsString()).contains("Content at the end");

    }
}
