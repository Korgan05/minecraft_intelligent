package lab.pupovina;

import net.minecraft.client.Minecraft;
import net.minecraft.util.text.StringTextComponent;
import net.minecraftforge.client.event.InputEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import org.lwjgl.glfw.GLFW;

/**
 * ПАУЗА по клавише P.
 *
 * Раньше паузу ловили через Windows, потому что иначе было никак. Но теперь
 * существо не отнимает мышь, и человек может нажать Escape в любой другой
 * программе — прошлый способ счёл бы это просьбой остановить обучение.
 *
 * Здесь клавиша слушается ВНУТРИ игры: событие приходит, только когда окно
 * впереди и не открыто меню. Сам мод ничего не останавливает — он лишь
 * поднимает флажок, а решает питон: там же живёт заморозка зомби.
 */
public final class Pauza {
    private static volatile boolean prosili;

    public static boolean prosili() {
        return prosili;
    }

    @SubscribeEvent
    public void klavisha(InputEvent.KeyInputEvent e) {
        if (e.getKey() != GLFW.GLFW_KEY_P || e.getAction() != GLFW.GLFW_PRESS) {
            return;
        }
        prosili = !prosili;
        Minecraft mc = Minecraft.getInstance();
        if (mc.player != null) {
            mc.player.displayClientMessage(
                    new StringTextComponent(prosili ? "§eПуповина: ПАУЗА"
                                                    : "§aПуповина: продолжаем"), true);
        }
    }
}
