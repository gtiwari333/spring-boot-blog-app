//package gt.app.web.mvc;
//
//import gt.app.domain.Note;
//import gt.app.modules.note.dto.NoteCreateDto;
//import gt.app.modules.note.dto.NoteEditDto;
//import jakarta.ws.rs.GET;
//import jakarta.ws.rs.POST;
//import jakarta.ws.rs.Path;
//import jakarta.ws.rs.PathParam;
//import gt.app.modules.note.NoteService;
//import lombok.RequiredArgsConstructor;
//import org.springframework.security.access.prepost.PreAuthorize;
//import org.springframework.stereotype.Controller;
//import org.springframework.ui.Model;
//import org.springframework.web.servlet.mvc.support.RedirectAttributes;
//
//@Controller
//@Path("/note")
//@RequiredArgsConstructor
//public class NoteController {
//
//    final NoteService noteService;
//
//    @POST
//    @Path("/add")
//    public String finishAddNote(NoteCreateDto noteDto, RedirectAttributes redirectAttrs) {
//        //TODO:validate and return to GET:/add on errors
//
//        Note note = noteService.createNote(noteDto);
//
//        redirectAttrs.addFlashAttribute("success", "Note with id " + note.getId() + " is created");
//
//        return "redirect:/";
//    }
//
//    @GET
//    @PreAuthorize("@permEvaluator.hasAccess(#id, 'Note' )")
//    @Path("/delete/{id}")
//    public String deleteNote(@PathParam(value = "id")  Long id, RedirectAttributes redirectAttrs) {
//        noteService.delete(id);
//
//        redirectAttrs.addFlashAttribute("success", "Note with id " + id + " is deleted");
//
//        return "redirect:/";
//    }
//
//    @GET
//    @PreAuthorize("@permEvaluator.hasAccess(#id, 'Note' )")
//    @Path("/edit/{id}")
//    public String startEditNote(Model model, @PathParam(value = "id")  Long id) {
//        model.addAttribute("msg", "Add a new note");
//        model.addAttribute("note", noteService.read(id));
//        return "note/edit-note";
//    }
//
//    @POST
//    @PreAuthorize("@permEvaluator.hasAccess(#noteDto.id, 'Note' )")
//    @Path("/edit")
//    public String finishEditNote(Model model, NoteEditDto noteDto, RedirectAttributes redirectAttrs) {
//        model.addAttribute("msg", "Add a new note");
//        //TODO:validate and return to GET:/edit/{id} on errors
//
//        noteService.update(noteDto);
//
//        redirectAttrs.addFlashAttribute("success", "Note with id " + noteDto.id() + " is updated");
//
//        return "redirect:/note";
//    }
//}
