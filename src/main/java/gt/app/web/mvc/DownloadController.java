//package gt.app.web.mvc;
//
//import gt.app.modules.file.FileDownloadUtil;
//import gt.app.modules.file.FileService;
//import gt.app.modules.file.ReceivedFileService;
//import gt.app.modules.file.RetrievalException;
//import jakarta.servlet.http.HttpServletResponse;
//import jakarta.ws.rs.GET;
//import jakarta.ws.rs.Path;
//import jakarta.ws.rs.PathParam;
//import lombok.RequiredArgsConstructor;
//import org.springframework.stereotype.Controller;
//
//import java.io.IOException;
//import java.util.UUID;
//
//@Controller
//@Path("/download")
//@RequiredArgsConstructor
//public class DownloadController {
//
//    final ReceivedFileService receivedFileService;
//    final FileService fileService;
//
//    @GET
//    @Path("/file/{id}")
//    //no security check needed
//    public void downloadFile(@PathParam(value = "id") UUID id, HttpServletResponse response) throws IOException {
//        var receivedFile = receivedFileService.findById(id)
//            .orElseThrow(() -> new RetrievalException("File not found", null));
//
//        var fileRes = fileService.loadAsResource(receivedFile.getFileGroup(), receivedFile.getStoredName());
//
//        FileDownloadUtil.downloadFile(response, fileRes.getURL(), receivedFile.getOriginalFileName());
//    }
//}
