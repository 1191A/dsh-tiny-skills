import java.awt.Color;
import java.awt.Dimension;
import java.awt.Graphics2D;
import java.awt.Rectangle;
import java.awt.RenderingHints;
import java.awt.image.BufferedImage;
import java.io.File;
import java.io.FileInputStream;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import javax.imageio.ImageIO;
import org.apache.poi.hslf.usermodel.HSLFShape;
import org.apache.poi.hslf.usermodel.HSLFSlide;
import org.apache.poi.hslf.usermodel.HSLFSlideShow;
import org.apache.poi.hslf.usermodel.HSLFTextShape;

/**
 * 把 .ppt（97-2003 二进制）逐页渲染成 PNG，同时导出每页文字。
 *
 * 用法: java -Djava.awt.headless=true RenderPpt in.ppt outdir [scale]
 *
 * 产出:
 *   outdir/s001.png ...     每页一张图（公式、图、版式都在里面）
 *   outdir/text.tsv         s001 \t 该页文字
 */
public class RenderPpt {
    public static void main(String[] args) throws Exception {
        if (args.length < 2) {
            System.err.println("usage: RenderPpt <in.ppt> <outdir> [scale]");
            System.exit(2);
        }
        String inPath = args[0];
        File outDir = new File(args[1]);
        float scale = args.length > 2 ? Float.parseFloat(args[2]) : 2.0f;
        if (!outDir.exists() && !outDir.mkdirs()) {
            System.err.println("cannot create " + outDir);
            System.exit(3);
        }

        HSLFSlideShow ppt = new HSLFSlideShow(new FileInputStream(inPath));
        Dimension size = ppt.getPageSize();
        int w = Math.round(size.width * scale);
        int h = Math.round(size.height * scale);

        PrintWriter tsv = new PrintWriter(new File(outDir, "text.tsv"), StandardCharsets.UTF_8);

        java.util.List<HSLFSlide> slides = ppt.getSlides();
        for (int i = 0; i < slides.size(); i++) {
            HSLFSlide slide = slides.get(i);
            String tag = String.format("s%03d", i + 1);

            BufferedImage img = new BufferedImage(w, h, BufferedImage.TYPE_INT_RGB);
            Graphics2D g = img.createGraphics();
            g.setPaint(Color.WHITE);
            g.fill(new Rectangle(0, 0, w, h));
            g.scale(scale, scale);
            g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
            g.setRenderingHint(RenderingHints.KEY_TEXT_ANTIALIASING, RenderingHints.VALUE_TEXT_ANTIALIAS_ON);
            g.setRenderingHint(RenderingHints.KEY_RENDERING, RenderingHints.VALUE_RENDER_QUALITY);
            g.setRenderingHint(RenderingHints.KEY_FRACTIONALMETRICS, RenderingHints.VALUE_FRACTIONALMETRICS_ON);
            slide.draw(g);
            g.dispose();
            ImageIO.write(img, "png", new File(outDir, tag + ".png"));

            StringBuilder sb = new StringBuilder();
            for (HSLFShape sh : slide.getShapes()) {
                if (sh instanceof HSLFTextShape) {
                    String t = ((HSLFTextShape) sh).getText();
                    if (t != null && !t.trim().isEmpty()) {
                        sb.append(t.trim()).append(" ⏎ ");
                    }
                }
            }
            tsv.println(tag + "\t" + sb.toString().replace("\t", " ").replace("\\n", " "));
            System.out.println("page " + tag);
        }
        tsv.close();
        System.out.println("pages=" + slides.size());
        ppt.close();
    }
}
