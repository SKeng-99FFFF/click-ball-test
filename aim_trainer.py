import pygame
import sys
import math
import random
import json
import os
from datetime import datetime

# 初始化pygame
pygame.init()

# 设置窗口比例 16:10，启用OPENGL支持和双缓冲以支持更好的垂直同步
screen_width = 1280
screen_height = 800
screen = pygame.display.set_mode((screen_width, screen_height), pygame.OPENGL | pygame.DOUBLEBUF)
pygame.display.set_caption("Aim Trainer - 目标训练 v3.0.5")

# 尝试启用垂直同步
try:
    pygame.display.gl_set_attribute(pygame.GL_SWAP_CONTROL, 1)
except:
    # 如果系统不支持VSync，则忽略
    pass

# 导入OpenGL库以支持垂直同步
try:
    from pygame.locals import *
    import OpenGL.GL as gl
except ImportError:
    # 如果OpenGL不可用，则使用普通双缓冲
    screen = pygame.display.set_mode((screen_width, screen_height), pygame.HWSURFACE | pygame.DOUBLEBUF)

# 颜色定义
BACKGROUND_COLOR = (204, 204, 204)  # #CCCCCC
BALL_COLOR = (249, 226, 175)  # #F9E2AF
TEXT_COLOR = (0, 0, 0)  # #000000
PANEL_COLOR = (240, 240, 240)
RED = (255, 0, 0)
BUTTON_COLOR = (100, 150, 200)
BUTTON_HOVER_COLOR = (120, 170, 220)

class ClickEffect:
    def __init__(self, x, y, score_text, duration=1000):  # 1秒持续时间
        self.x = x
        self.y = y
        self.score_text = score_text
        self.start_time = pygame.time.get_ticks()
        self.duration = duration
        self.font = pygame.font.Font(None, 36)
        # 缓存文本表面以提高性能
        self.cached_text_surface = self.font.render(str(score_text), True, TEXT_COLOR)
        
    def is_finished(self):
        current_time = pygame.time.get_ticks()
        return current_time - self.start_time >= self.duration
    
    def get_alpha(self):
        current_time = pygame.time.get_ticks()
        elapsed = current_time - self.start_time
        if elapsed >= self.duration:
            return 0
        
        # 前1秒正常显示，后2秒逐渐透明
        if elapsed <= 1000:
            return 255  # 完全不透明
        else:
            remaining = 3000 - elapsed  # 总共3秒，后2秒逐渐透明
            alpha = int((remaining / 2000) * 255)
            return max(0, alpha)
    
    def draw(self, surface):
        alpha = self.get_alpha()
        if alpha <= 0:
            return
            
        # 使用缓存的文本表面以提高性能
        if alpha < 255:
            # 创建带透明度的副本
            text_surface = self.cached_text_surface.copy()
            text_surface.set_alpha(alpha)
        else:
            text_surface = self.cached_text_surface
        
        # 居中显示在点击位置
        text_rect = text_surface.get_rect(center=(int(self.x), int(self.y)))
        surface.blit(text_surface, text_rect)

class Ball:
    def __init__(self, x, y, radius, color=BALL_COLOR):
        self.x = x
        self.y = y
        self.radius = radius
        self.color = color
    
    def draw(self, surface):
        # 使用抗锯齿绘制圆形以改善渲染质量
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), int(self.radius))
        # 添加抗锯齿边缘
        pygame.draw.circle(surface, (0, 0, 0), (int(self.x), int(self.y)), int(self.radius), 1)

class AimTrainer:
    def __init__(self, game_mode="mod_1", game_duration=60000):
        self.game_mode = game_mode  # "mod_1" 或 "mod_2"
        
        """
        ========================================
        变量表 - 优化的变量结构设计
        ========================================
        
        1. 通用变量 (两个模式都使用)
        """
        self.game_duration = game_duration  # 游戏持续时间 (毫秒)
        self.n = 3  # 同时显示的小球数量
        self.C = 100  # 基础分数 (模式2和3为100分)
        self.history_file = "aim_trainer_history.json"  # 历史记录文件
        self.panel_width = 250  # 信息面板宽度
        self.panel_height = screen_height  # 信息面板高度
        self.panel_x = screen_width - self.panel_width  # 信息面板X坐标
        self.panel_y = 0  # 信息面板Y坐标
        self.game_width = screen_width - self.panel_width  # 游戏区域宽度
        self.game_height = screen_height  # 游戏区域高度
        
        # 字体相关
        pygame.font.init()
        self.font_large = pygame.font.Font(None, 48)
        self.font_medium = pygame.font.Font(None, 36)
        self.font_small = pygame.font.Font(None, 24)
        
        """
        2. 基于数学对应关系的变量 (通过基础变量和比例关系计算得出)
        """
        # 基础网格大小 (两个模式共享)
        self.base_grid_size = int(min(self.game_width, self.game_height) * 0.08)
        
        # 模式特定的比例参数
        if self.game_mode == "mod_1":
            self.ball_diameter_ratio = 1.0  # 模式1: 球体直径比例 (基准)
            self.grid_ball_ratio = 1.5      # 模式1: 方格与球体直径比例
        elif self.game_mode == "mod_2":
            self.ball_diameter_ratio = 1.75 # 模式2: 球体直径是模式1的1.75倍
            self.grid_ball_ratio = 1.3      # 模式2: 方格边长是球体直径的1.3倍
        else:  # mod_3
            self.ball_diameter_ratio = 1.75 # 模式3: 球体直径是模式1的1.75倍（复用模式2规则）
            self.grid_ball_ratio = 1.3      # 模式3: 方格边长是球体直径的1.3倍（复用模式2规则）
        
        # 通过数学关系计算得出的实际值
        self.base_ball_diameter = (self.base_grid_size // 2) * 2 - 4  # 基础球体直径
        self.actual_ball_diameter = int(self.base_ball_diameter * self.ball_diameter_ratio)  # 实际球体直径
        self.ball_radius = self.actual_ball_diameter // 2  # 实际球体半径
        self.grid_size = int(self.actual_ball_diameter * self.grid_ball_ratio)  # 实际方格边长
        
        # 计算网格行列数
        self.cols = self.game_width // self.grid_size
        self.rows = self.game_height // self.grid_size
        
        """
        3. 专用变量 (每个模式特有的变量和游戏状态)
        """
        # 游戏状态变量
        self.balls = []
        self.score = 0
        self.total_clicks = 0
        self.hit_clicks = 0
        self.start_time = None
        self.game_active = True
        self.game_end_time = None
        self.combo_count = 0  # 连击计数
        
        # 位置记录和生成规则 (模式特定)
        self.last_ball_positions = []  # 记录最后消失的小球位置
        
        # 点击效果
        self.click_effects = []
        
        # 点击时间记录
        self.click_times = []
        self.first_click_time = None  # 第一次点击的时间
        
        # 模式3特定变量
        if self.game_mode == "mod_3":
            # 背景板偏移量
            self.offset_x = 0
            self.offset_y = 0
            # 背景板原始位置（用于重置）
            self.original_balls_positions = []
            # 中心位置
            self.center_x = self.game_width // 2
            self.center_y = self.game_height // 2
            # 背景板移动速度控制
            self.background_movable = True
        
        # 加载历史记录
        self.load_history()
        
        self.initialize_game()
        
        # 模式3特殊设置：隐藏光标
        if self.game_mode == "mod_3":
            pygame.mouse.set_visible(False)
    
    def get_combo_threshold(self):
        """根据当前同屏小球数量计算连击阈值"""
        current_balls = len(self.balls)
        max_balls = self.n
        
        # 提高阈值，使奖励更难获得
        threshold = 2 * max_balls - current_balls + 1
        
        return max(2, threshold)  # 确保至少为2
    
    def get_combo_bonus(self):
        """根据当前同屏小球数量计算连击奖励"""
        current_balls = len(self.balls)
        max_balls = self.n
        
        # 基础奖励大幅降低
        base_bonus = 2  # 从原来的7大幅降低
        
        # 当小球数量减少时，奖励略有增加
        bonus_multiplier = 1.0 + (max_balls - current_balls) * 0.1  # 从0.2降低到0.1
        
        return int(base_bonus * bonus_multiplier)
    
    def calculate_current_ball_score(self):
        """根据当前连击数和同屏小球数量计算当前小球的分数"""
        combo_threshold = self.get_combo_threshold()
        combo_bonus = self.get_combo_bonus()
        
        # 计算当前奖励级别
        bonus_level = self.combo_count // combo_threshold
        current_score = self.C + bonus_level * combo_bonus
        
        return int(current_score)
    
    def get_available_positions(self):
        """获取可用的网格位置"""
        available_positions = []
        
        if self.game_mode == "mod_1":
            # 模式1：全区域，最多3个小球
            start_row, end_row = 1, self.rows - 1
            start_col, end_col = 1, self.cols - 1
            # 记录n-1个最后消失的位置
            positions_to_check = self.last_ball_positions[-(self.n-1):] if self.n > 1 else []
        elif self.game_mode == "mod_2":
            # 模式2：只在中间3x3区域（9个格子），最多3个小球
            center_row = self.rows // 2
            center_col = self.cols // 2
            start_row = max(1, center_row - 1)  # 3x3中心区域
            end_row = min(self.rows - 1, center_row + 2)
            start_col = max(1, center_col - 1)
            end_col = min(self.cols - 1, center_col + 2)
            # 记录n+1个最后消失的位置
            positions_to_check = self.last_ball_positions[-(self.n+1):]  # n=3, 所以记录4个位置
        else:  # mod_3
            # 模式3：复用模式2的生成规则（中间3x3区域，最多3个小球）
            center_row = self.rows // 2
            center_col = self.cols // 2
            start_row = max(1, center_row - 1)  # 3x3中心区域
            end_row = min(self.rows - 1, center_row + 2)
            start_col = max(1, center_col - 1)
            end_col = min(self.cols - 1, center_col + 2)
            # 记录n+1个最后消失的位置
            positions_to_check = self.last_ball_positions[-(self.n+1):]  # n=3, 所以记录4个位置
        
        # 生成网格位置
        for row in range(start_row, end_row):
            for col in range(start_col, end_col):
                # 球体圆心在方格的对角线交线上（方格中心）
                x = col * self.grid_size + self.grid_size // 2
                y = row * self.grid_size + self.grid_size // 2
                
                # 模式1：检查与现有小球的距离（保持原有规则）
                # 模式2和模式3：根据新的方格-球体关系设置
                too_close = False
                
                if self.game_mode == "mod_1":
                    # 模式1：检查与现有小球的距离
                    for ball in self.balls:
                        distance = math.sqrt((x - ball.x) ** 2 + (y - ball.y) ** 2)
                        if distance < self.grid_size * 1.5:  # 间距至少1.5倍网格大小
                            too_close = True
                            break
                else:  # mod_2 or mod_3
                    # 模式2和模式3：由于球体变大了，需要确保不重叠
                    min_distance = self.ball_radius * 2 * 1.2  # 稍微增加安全距离
                    
                    for ball in self.balls:
                        distance = math.sqrt((x - ball.x) ** 2 + (y - ball.y) ** 2)
                        if distance < min_distance:
                            too_close = True
                            break
                
                # 检查是否与最近消失的位置太近
                if not too_close:
                    for last_pos in positions_to_check:
                        if last_pos is None:
                            continue
                        # 对于模式2和模式3，使用适当的距离检查
                        distance = math.sqrt((x - last_pos[0]) ** 2 + (y - last_pos[1]) ** 2)
                        # 使用网格大小来避免在原位置生成
                        if distance < self.grid_size * 0.8:  # 使用网格大小的一定比例
                            too_close = True
                            break
                
                if not too_close:
                    available_positions.append((x, y))
        
        return available_positions
    
    def initialize_game(self):
        """初始化游戏状态"""
        self.balls = []
        self.score = 0
        self.total_clicks = 0
        self.hit_clicks = 0
        self.combo_count = 0
        self.last_ball_positions = []
        self.click_effects = []
        self.click_times = []
        self.first_click_time = None
        self.start_time = None  # 不在初始化时开始计时
        self.game_active = True
        self.game_end_time = None
        
        # 恢复光标显示（为新模式做准备）
        if self.game_mode == "mod_3":
            pygame.mouse.set_visible(False)
        else:
            pygame.mouse.set_visible(True)
        
        # 生成n个小球
        self.generate_balls(self.n)
    
    def generate_balls(self, count):
        """生成指定数量的小球"""
        available_positions = self.get_available_positions()
        
        if not available_positions:
            # 如果没有可用位置，放宽限制
            available_positions = self.get_relaxed_available_positions()
        
        if not available_positions:
            return  # 没有可用位置
        
        # 随机选择位置
        random.shuffle(available_positions)
        
        for i in range(min(count, len(available_positions))):
            x, y = available_positions[i]
            ball = Ball(x, y, self.ball_radius)
            self.balls.append(ball)
    
    def get_relaxed_available_positions(self):
        """获取放宽限制的可用位置（当严格限制下没有可用位置时）"""
        available_positions = []
        
        if self.game_mode == "mod_1":
            # 模式1：全区域
            start_row, end_row = 1, self.rows - 1
            start_col, end_col = 1, self.cols - 1
        else:  # mod_2 or mod_3
            # 模式2和模式3：只在中间3x3区域
            center_row = self.rows // 2
            center_col = self.cols // 2
            start_row = max(1, center_row - 1)
            end_row = min(self.rows - 1, center_row + 2)
            start_col = max(1, center_col - 1)
            end_col = min(self.cols - 1, center_col + 2)
        
        # 生成网格位置
        for row in range(start_row, end_row):
            for col in range(start_col, end_col):
                x = col * self.grid_size + self.grid_size // 2  # 方格中心
                y = row * self.grid_size + self.grid_size // 2
                
                # 只检查与现有小球的重叠，不检查原位置
                too_close = False
                if self.game_mode == "mod_1":
                    # 模式1使用原始规则
                    for ball in self.balls:
                        distance = math.sqrt((x - ball.x) ** 2 + (y - ball.y) ** 2)
                        min_distance = self.ball_radius * 2 * 0.8
                        if distance < min_distance:
                            too_close = True
                            break
                else:  # mod_2 or mod_3
                    # 模式2和模式3使用更大的球体半径
                    min_distance = self.ball_radius * 2 * 1.0  # 放宽到1.0倍
                    
                    for ball in self.balls:
                        distance = math.sqrt((x - ball.x) ** 2 + (y - ball.y) ** 2)
                        if distance < min_distance:
                            too_close = True
                            break
                
                if not too_close:
                    available_positions.append((x, y))
        
        return available_positions
    
    def handle_mouse_motion(self, pos):
        """处理鼠标移动事件（仅模式3）"""
        if self.game_mode == "mod_3" and self.game_active and self.background_movable:
            # 计算鼠标相对于游戏区域中心的偏移（反向移动以营造移动中心的感觉）
            self.offset_x = self.center_x - pos[0]  # 反向：鼠标向右移动，背景向左移动
            self.offset_y = self.center_y - pos[1]  # 反向：鼠标向下移动，背景向上移动
    
    def handle_click(self, pos):
        """处理点击事件"""
        if not self.game_active:
            return
        
        # 记录点击时间（用于平均间隔计算，但只记录正确点击）
        current_time = pygame.time.get_ticks()
        
        # 第一次点击时开始游戏计时
        if self.first_click_time is None:
            self.first_click_time = current_time
        if self.start_time is None:
            self.start_time = current_time
        
        # 检查是否点击在游戏区域内（不在面板上）
        if pos[0] >= self.game_width:
            # 错误点击，扣分
            self.total_clicks += 1
            self.score -= 100  # 现在允许负分
            self.combo_count = 0  # 重置连击计数
            return
        
        self.total_clicks += 1
        
        if self.game_mode == "mod_3":
            # 模式3：检查中心点是否在任意小球上
            clicked_ball = None
            # 检查移动后的小球位置（加上偏移量）
            for ball in self.balls:
                # 计算移动后的小球中心位置
                moved_ball_x = ball.x + self.offset_x
                moved_ball_y = ball.y + self.offset_y
                
                # 检查中心点是否在移动后的小球范围内（这是关键：中心点在小球上就算正确）
                distance_center_to_ball = math.sqrt((self.center_x - moved_ball_x) ** 2 + (self.center_y - moved_ball_y) ** 2)
                
                # 如果中心点在小球范围内，则算作正确点击（无论点击位置在哪里）
                if distance_center_to_ball <= self.ball_radius:
                    clicked_ball = ball
                    # 保存原始位置用于记录
                    original_x, original_y = ball.x, ball.y
                    break
            
            if clicked_ball:
                # 点击到小球，加分
                self.balls.remove(clicked_ball)
                
                # 记录小球消失的位置（原始位置）
                self.last_ball_positions.append((original_x, original_y))
                if len(self.last_ball_positions) > 20:  # 只保留最近20个位置
                    self.last_ball_positions.pop(0)
                
                self.hit_clicks += 1
                
                # 只有正确点击才记录到click_times用于间隔计算
                self.click_times.append(current_time)
                
                # 计算当前分数（根据连击数和当前同屏小球数量）
                current_ball_score = self.calculate_current_ball_score()
                self.score += current_ball_score
                
                # 模式3不创建点击效果
                if self.game_mode != "mod_3":
                    # 创建点击效果（在移动后的位置显示）
                    effect_x = original_x + self.offset_x
                    effect_y = original_y + self.offset_y
                    effect = ClickEffect(effect_x, effect_y, f"+{current_ball_score}")
                    self.click_effects.append(effect)
                
                # 增加连击计数
                self.combo_count += 1
                
                # 生成新的小球（点击后立即生成）
                self.generate_balls(1)
            else:
                # 点击空白区域或中心点不在任何小球上，扣分
                self.score -= 100  # 允许负分
                self.combo_count = 0  # 重置连击计数
        else:
            # 模式1和模式2：原始点击逻辑
            clicked_ball = None
            
            # 检查是否点击到小球
            for ball in self.balls[:]:  # 使用副本进行遍历
                distance = math.sqrt((pos[0] - ball.x) ** 2 + (pos[1] - ball.y) ** 2)
                if distance <= ball.radius:
                    clicked_ball = ball
                    break
            
            if clicked_ball:
                # 点击到小球，加分
                self.balls.remove(clicked_ball)
                
                # 记录小球消失的位置
                self.last_ball_positions.append((clicked_ball.x, clicked_ball.y))
                if len(self.last_ball_positions) > 20:  # 只保留最近20个位置
                    self.last_ball_positions.pop(0)
                
                self.hit_clicks += 1
                
                # 只有正确点击才记录到click_times用于间隔计算
                self.click_times.append(current_time)
                
                # 计算当前分数（根据连击数和当前同屏小球数量）
                current_ball_score = self.calculate_current_ball_score()
                self.score += current_ball_score
                
                # 模式3不创建点击效果
                if self.game_mode != "mod_3":
                    # 创建点击效果
                    effect = ClickEffect(pos[0], pos[1], f"+{current_ball_score}")
                    self.click_effects.append(effect)
                
                # 增加连击计数
                self.combo_count += 1
                
                # 生成新的小球（点击后立即生成）
                self.generate_balls(1)
            else:
                # 点击空白区域，扣分
                self.score -= 100  # 允许负分
                self.combo_count = 0  # 重置连击计数
    
    def calculate_average_click_interval(self):
        """计算平均两次正确点击的时间间隔（毫秒）"""
        if len(self.click_times) < 2:
            return 0.0
        
        # 计算相邻点击的时间间隔
        intervals = []
        for i in range(1, len(self.click_times)):
            interval = self.click_times[i] - self.click_times[i-1]
            intervals.append(interval)
        
        if intervals:
            avg_interval = sum(intervals) / len(intervals)
            return round(avg_interval, 3)  # 保留3位小数
        return 0.0
    
    def calculate_score_display(self):
        """计算用于显示的分数（游戏结束后保持不变）"""
        if not self.game_active and hasattr(self, 'final_score'):
            return self.final_score
        return self.score
    
    def save_result(self):
        """保存游戏结果到历史记录"""
        if self.start_time is None or self.total_clicks == 0:
            return
        
        result = {
            "timestamp": datetime.now().isoformat(),
            "score": self.score,
            "total_clicks": self.total_clicks,
            "hit_clicks": self.hit_clicks,
            "accuracy": self.hit_clicks / self.total_clicks if self.total_clicks > 0 else 0,
            "time_elapsed": (pygame.time.get_ticks() - self.start_time) / 1000.0 if self.start_time else 0,
            "max_combo": self.combo_count,
            "max_balls": self.n,
            "avg_click_interval": self.calculate_average_click_interval(),
            "game_mode": self.game_mode
        }
        
        history = []
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            except:
                history = []
        
        history.append(result)
        
        # 只保留最近100条记录
        history = history[-100:]
        
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    
    def load_history(self):
        """加载历史记录"""
        self.history = []
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self.history = json.load(f)
            except:
                self.history = []
    
    def get_statistics(self):
        """获取统计信息"""
        # 分别统计不同模式的历史记录
        mode_history = [r for r in self.history if r.get('game_mode', 'mod_1') == self.game_mode]
        
        if not mode_history:
            return f"{self.game_mode}: No history"
        
        scores = [r['score'] for r in mode_history]
        avg_score = sum(scores) / len(scores)
        best_score = max(scores)
        total_games = len(mode_history)
        
        return f"{self.game_mode}: G:{total_games} Avg:{int(avg_score)} Best:{best_score}"
    
    def check_game_end(self):
        """检查游戏是否应该结束"""
        if not self.game_active:
            return False
        
        current_time = pygame.time.get_ticks()
        # 从第一次点击开始计算游戏时间
        if self.first_click_time is not None:
            time_elapsed = current_time - self.first_click_time
        else:
            time_elapsed = current_time - (self.start_time or current_time)
        
        # 游戏时间到达指定时间后结束
        if time_elapsed >= self.game_duration:
            self.game_active = False
            self.game_end_time = current_time
            self.final_score = self.score  # 保存最终分数
            self.save_result()
            
            # 游戏结束时恢复光标显示
            pygame.mouse.set_visible(True)
            
            return True
        
        return False
    
    def draw_info_panel(self):
        """绘制信息面板"""
        # 绘制面板背景
        panel_rect = pygame.Rect(self.panel_x, self.panel_y, self.panel_width, self.panel_height)
        pygame.draw.rect(screen, PANEL_COLOR, panel_rect)
        pygame.draw.line(screen, TEXT_COLOR, (self.panel_x, 0), (self.panel_x, screen_height), 2)
        
        # 绘制信息 - 使用新颜色
        y_offset = 20
        score_text = self.font_medium.render(f"Score: {self.calculate_score_display()}", True, TEXT_COLOR)
        screen.blit(score_text, (self.panel_x + 10, y_offset))
        
        y_offset += 40
        accuracy = self.hit_clicks / self.total_clicks if self.total_clicks > 0 else 0
        accuracy_text = self.font_medium.render(f"Accuracy: {accuracy:.2%}", True, TEXT_COLOR)
        screen.blit(accuracy_text, (self.panel_x + 10, y_offset))
        
        y_offset += 40
        clicks_text = self.font_medium.render(f"Clicks: {self.hit_clicks}/{self.total_clicks}", True, TEXT_COLOR)
        screen.blit(clicks_text, (self.panel_x + 10, y_offset))
        
        y_offset += 40
        combo_text = self.font_medium.render(f"Combo: {self.combo_count}", True, TEXT_COLOR)
        screen.blit(combo_text, (self.panel_x + 10, y_offset))
        
        y_offset += 40
        # 显示当前小球的分数和连击参数
        current_ball_score = self.calculate_current_ball_score()
        combo_threshold = self.get_combo_threshold()
        combo_bonus = self.get_combo_bonus()
        ball_score_text = self.font_medium.render(f"Ball: {current_ball_score} (T:{combo_threshold},B:{combo_bonus})", True, TEXT_COLOR)
        screen.blit(ball_score_text, (self.panel_x + 10, y_offset))
        
        # 显示当前同屏小球数
        y_offset += 40
        current_balls_text = self.font_medium.render(f"Balls: {len(self.balls)}/{self.n}", True, TEXT_COLOR)
        screen.blit(current_balls_text, (self.panel_x + 10, y_offset))
        
        # 显示平均点击间隔
        if len(self.click_times) >= 2:
            y_offset += 40
            avg_interval = self.calculate_average_click_interval()
            interval_text = self.font_medium.render(f"Int(ms): {avg_interval:.3f}", True, TEXT_COLOR)
            screen.blit(interval_text, (self.panel_x + 10, y_offset))
        
        # 显示当前模式
        y_offset += 40
        mode_text = self.font_medium.render(f"Mode: {self.game_mode}", True, TEXT_COLOR)
        screen.blit(mode_text, (self.panel_x + 10, y_offset))
        
        # 显示剩余时间
        if self.start_time is not None and self.game_active:
            y_offset += 40
            current_time = pygame.time.get_ticks()
            # 从第一次点击开始计算剩余时间
            if self.first_click_time is not None:
                time_elapsed = current_time - self.first_click_time
            else:
                time_elapsed = current_time - self.start_time
            remaining_time = max(0, self.game_duration - time_elapsed)
            remaining_seconds = remaining_time / 1000.0
            time_text = self.font_medium.render(f"Time: {remaining_seconds:.1f}s", True, TEXT_COLOR)
            screen.blit(time_text, (self.panel_x + 10, y_offset))
        elif not self.game_active:
            y_offset += 40
            time_text = self.font_medium.render("Time: 0.0s", True, TEXT_COLOR)
            screen.blit(time_text, (self.panel_x + 10, y_offset))
        
        # 绘制操作提示
        y_offset = self.game_height - 80
        instruction_text = self.font_small.render("Click red balls", True, TEXT_COLOR)
        screen.blit(instruction_text, (self.panel_x + 10, y_offset))
        
        # 绘制统计信息
        y_offset = self.game_height - 40
        stats_text = self.font_small.render(self.get_statistics(), True, TEXT_COLOR)
        screen.blit(stats_text, (self.panel_x + 10, y_offset))
    
    def draw(self):
        """绘制游戏界面"""
        # 创建一个临时表面用于双缓冲
        game_surface = pygame.Surface((self.game_width, self.game_height))
        
        # 绘制游戏区域背景
        game_rect = pygame.Rect(0, 0, self.game_width, self.game_height)
        pygame.draw.rect(game_surface, BACKGROUND_COLOR, game_rect)
        
        # 绘制中心标记（模式3用，也可以用于其他模式参考）
        if self.game_mode == "mod_3":
            # 绘制中心十字标记
            center_x = self.center_x
            center_y = self.center_y
            pygame.draw.line(game_surface, (255, 0, 0), (center_x - 20, center_y), (center_x + 20, center_y), 2)
            pygame.draw.line(game_surface, (255, 0, 0), (center_x, center_y - 20), (center_x, center_y + 20), 2)
        
        # 绘制小球（游戏结束后继续显示剩余小球，模式3需要应用偏移）
        for ball in self.balls:
            if self.game_mode == "mod_3":
                # 模式3：绘制移动后的位置 - 直接计算，避免创建临时对象
                x = int(ball.x + self.offset_x)
                y = int(ball.y + self.offset_y)
                pygame.draw.circle(game_surface, ball.color, (x, y), int(ball.radius))
                # 添加抗锯齿边缘
                pygame.draw.circle(game_surface, (0, 0, 0), (x, y), int(ball.radius), 1)
            else:
                # 模式1和2：正常绘制
                pygame.draw.circle(game_surface, ball.color, (int(ball.x), int(ball.y)), int(ball.radius))
                # 添加抗锯齿边缘
                pygame.draw.circle(game_surface, (0, 0, 0), (int(ball.x), int(ball.y)), int(ball.radius), 1)
        
        # 绘制点击效果（模式3需要应用偏移）
        for effect in self.click_effects[:]:
            if self.game_mode == "mod_3":
                # 模式3：调整点击效果位置 - 直接计算，避免创建临时对象
                original_x = effect.x - (getattr(self, 'offset_x', 0) if hasattr(self, 'offset_x') else 0)
                original_y = effect.y - (getattr(self, 'offset_y', 0) if hasattr(self, 'offset_y') else 0)
                # 直接计算显示位置
                display_x = int(original_x + self.offset_x)
                display_y = int(original_y + self.offset_y)
                alpha = effect.get_alpha()
                if alpha > 0:
                    # 创建文本表面
                    text_surface = effect.font.render(str(effect.score_text), True, TEXT_COLOR)
                    if alpha < 255:
                        text_surface.set_alpha(alpha)
                    # 居中显示在点击位置
                    text_rect = text_surface.get_rect(center=(display_x, display_y))
                    game_surface.blit(text_surface, text_rect)
            else:
                alpha = effect.get_alpha()
                if alpha > 0:
                    text_surface = effect.font.render(str(effect.score_text), True, TEXT_COLOR)
                    if alpha < 255:
                        text_surface.set_alpha(alpha)
                    # 居中显示在点击位置
                    text_rect = text_surface.get_rect(center=(int(effect.x), int(effect.y)))
                    game_surface.blit(text_surface, text_rect)
            
            if effect.is_finished():
                self.click_effects.remove(effect)
        
        # 将游戏表面绘制到屏幕上
        screen.blit(game_surface, (0, 0))
        
        # 绘制信息面板（直接绘制到主屏幕）
        self.draw_info_panel()
        
        # 绘制游戏结束提示
        if not self.game_active and self.game_end_time:
            # 在游戏区域中央显示结束信息
            center_x = self.game_width // 2
            center_y = self.game_height // 2
            
            game_over_text = self.font_large.render("Game Over!", True, RED)
            screen.blit(game_over_text, (center_x - game_over_text.get_width()//2, center_y - 30))
            
            restart_text = self.font_medium.render("Click to restart", True, TEXT_COLOR)
            screen.blit(restart_text, (center_x - restart_text.get_width()//2, center_y + 30))

class ModeSelection:
    def __init__(self):
        self.font_large = pygame.font.Font(None, 72)
        self.font_medium = pygame.font.Font(None, 36)
        self.font_small = pygame.font.Font(None, 24)
        
        # 按钮设置 - 三个模式水平排列
        center_x = screen_width // 2
        button_width = 120
        button_height = 60
        spacing = 150  # 按钮间距
        
        # 计算三个按钮的位置，使它们居中
        total_width = 3 * button_width + 2 * spacing
        start_x = center_x - total_width // 2
        
        self.mod1_button = pygame.Rect(start_x, screen_height // 2 - 50, button_width, button_height)
        self.mod2_button = pygame.Rect(start_x + button_width + spacing, screen_height // 2 - 50, button_width, button_height)
        self.mod3_button = pygame.Rect(start_x + 2 * (button_width + spacing), screen_height // 2 - 50, button_width, button_height)
        
    def draw(self):
        """绘制模式选择界面"""
        # 清空屏幕
        screen.fill(BACKGROUND_COLOR)
        
        # 标题
        title_text = self.font_large.render("Aim Trainer", True, TEXT_COLOR)
        title_rect = title_text.get_rect(center=(screen_width // 2, screen_height // 4))
        screen.blit(title_text, title_rect)
        
        # 模式选择说明
        info_text = self.font_medium.render("Select Game Mode:", True, TEXT_COLOR)
        info_rect = info_text.get_rect(center=(screen_width // 2, screen_height // 3))
        screen.blit(info_text, info_rect)
        
        # 模式1按钮
        mouse_pos = pygame.mouse.get_pos()
        mod1_hover = self.mod1_button.collidepoint(mouse_pos)
        button_color = BUTTON_HOVER_COLOR if mod1_hover else BUTTON_COLOR
        pygame.draw.rect(screen, button_color, self.mod1_button)
        pygame.draw.rect(screen, TEXT_COLOR, self.mod1_button, 3)
        mod1_text = self.font_medium.render("Mode 1", True, TEXT_COLOR)
        mod1_rect = mod1_text.get_rect(center=self.mod1_button.center)
        screen.blit(mod1_text, mod1_rect)
        
        # 模式2按钮
        mod2_hover = self.mod2_button.collidepoint(mouse_pos)
        button_color = BUTTON_HOVER_COLOR if mod2_hover else BUTTON_COLOR
        pygame.draw.rect(screen, button_color, self.mod2_button)
        pygame.draw.rect(screen, TEXT_COLOR, self.mod2_button, 3)
        mod2_text = self.font_medium.render("Mode 2", True, TEXT_COLOR)
        mod2_rect = mod2_text.get_rect(center=self.mod2_button.center)
        screen.blit(mod2_text, mod2_rect)
        
        # 模式3按钮
        mod3_hover = self.mod3_button.collidepoint(mouse_pos)
        button_color = BUTTON_HOVER_COLOR if mod3_hover else BUTTON_COLOR
        pygame.draw.rect(screen, button_color, self.mod3_button)
        pygame.draw.rect(screen, TEXT_COLOR, self.mod3_button, 3)
        mod3_text = self.font_medium.render("Mode 3", True, TEXT_COLOR)
        mod3_rect = mod3_text.get_rect(center=self.mod3_button.center)
        screen.blit(mod3_text, mod3_rect)
        
        # 模式说明
        mod1_desc = self.font_small.render("Normal grid, full area", True, TEXT_COLOR)
        mod1_desc_rect = mod1_desc.get_rect(center=(self.mod1_button.centerx, self.mod1_button.bottom + 30))
        screen.blit(mod1_desc, mod1_desc_rect)
        
        mod2_desc = self.font_small.render("Larger balls, 3x3 center", True, TEXT_COLOR)
        mod2_desc_rect = mod2_desc.get_rect(center=(self.mod2_button.centerx, self.mod2_button.bottom + 30))
        screen.blit(mod2_desc, mod2_desc_rect)
        
        mod3_desc = self.font_small.render("Move board, center click", True, TEXT_COLOR)
        mod3_desc_rect = mod3_desc.get_rect(center=(self.mod3_button.centerx, self.mod3_button.bottom + 30))
        screen.blit(mod3_desc, mod3_desc_rect)
        
        # ESC提示
        esc_text = self.font_small.render("Press ESC to return", True, TEXT_COLOR)
        esc_rect = esc_text.get_rect(center=(screen_width // 2, screen_height - 50))
        screen.blit(esc_text, esc_rect)
    
    def handle_click(self, pos):
        """处理模式选择点击"""
        if self.mod1_button.collidepoint(pos):
            return "mod_1"
        elif self.mod2_button.collidepoint(pos):
            return "mod_2"
        elif self.mod3_button.collidepoint(pos):
            return "mod_3"
        return None
    
    def is_button_hovered(self, pos):
        """检查鼠标是否悬停在按钮上"""
        return self.mod1_button.collidepoint(pos) or self.mod2_button.collidepoint(pos) or self.mod3_button.collidepoint(pos)

def main():
    clock = pygame.time.Clock()
    current_state = "mode_selection"  # "mode_selection" or "game"
    game = None
    mode_selector = ModeSelection()
    
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if current_state == "game":
                        # ESC返回模式选择，恢复光标显示
                        pygame.mouse.set_visible(True)
                        current_state = "mode_selection"
                        game = None
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # 左键点击
                    if current_state == "mode_selection":
                        selected_mode = mode_selector.handle_click(event.pos)
                        if selected_mode:
                            game = AimTrainer(game_mode=selected_mode, game_duration=60000)
                            current_state = "game"
                    elif current_state == "game" and game:
                        if not game.game_active and game.game_end_time and pygame.time.get_ticks() - game.game_end_time > 500:  # 防止误点击
                            game.initialize_game()
                        else:
                            game.handle_click(event.pos)
            elif event.type == pygame.MOUSEMOTION:
                # 处理鼠标移动事件（仅模式3）
                if current_state == "game" and game and game.game_active:
                    game.handle_mouse_motion(event.pos)
        
        if current_state == "mode_selection":
            mode_selector.draw()
        elif current_state == "game" and game:
            # 检查游戏是否结束
            game.check_game_end()
            
            game.draw()
        
        # 尝试使用OpenGL交换缓冲区以启用垂直同步
        try:
            pygame.display.flip()  # 这会使用设置的双缓冲
        except:
            # 如果OpenGL不可用，则使用普通更新
            pygame.display.flip()
        
        # 限制帧率为240 FPS，支持高刷新率显示器
        clock.tick(240)
    
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()