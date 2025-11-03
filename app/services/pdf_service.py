from datetime import datetime
from app.models.activity import UserReport
import io
import os
import logging
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

logger = logging.getLogger(__name__)

def register_korean_fonts():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    base_path = os.path.join(current_dir, '..', 'utils', 'format', 'fonts')
    
    regular_font_path = os.path.join(base_path, 'NotoSansKR-Regular.ttf')
    bold_font_path = os.path.join(base_path, 'NotoSansKR-Bold.ttf')

    # 폰트 파일 존재 여부 확인
    if not os.path.exists(regular_font_path) or not os.path.exists(bold_font_path):
        logger.error(f"폰트 파일 경로를 찾을 수 없습니다.")
        logger.error(f"Regular 경로: {regular_font_path}")
        logger.error(f"Bold 경로: {bold_font_path}")
        return False, None

    try:
        # ReportLab 한글 폰트 등록
        pdfmetrics.registerFont(TTFont('NotoSansKR-Regular', regular_font_path))
        pdfmetrics.registerFont(TTFont('NotoSansKR-Bold', bold_font_path))
        
        # 폰트 패밀리 등록
        from reportlab.pdfbase.pdfmetrics import registerFontFamily
        registerFontFamily('NotoSansKR',
                         normal='NotoSansKR-Regular',
                         bold='NotoSansKR-Bold')
        
        # Matplotlib 폰트 등록 및 설정
        try:
            # 폰트 파일을 Matplotlib에 추가
            font_prop = fm.FontProperties(fname=regular_font_path)
            font_name = font_prop.get_name()
            
            fm.fontManager.addfont(regular_font_path)
            
            # Matplotlib 전역 설정
            plt.rcParams['font.family'] = font_name
            plt.rcParams['axes.unicode_minus'] = False
            
            logger.info(f"Matplotlib 폰트 등록 완료: {font_name}")
        except Exception as e:
            logger.warning(f"Matplotlib 폰트 등록 실패: {e}")
            return True, None  # ReportLab은 성공했으므로 계속 진행

        logger.info("한글 폰트 등록 완료")
        return True, regular_font_path
        
    except Exception as e:
        logger.error(f"폰트 등록 실패: {e}")
        return False, None

def generate_activity_bar_chart_buffer(stats, font_path=None) -> io.BytesIO:
    total_activities = getattr(stats, 'total_activities', 0)
    total_hours = getattr(stats, 'total_hours', 0.0)

    # 폰트 설정
    if font_path and os.path.exists(font_path):
        try:
            font_prop = fm.FontProperties(fname=font_path)
            plt.rcParams['font.family'] = font_prop.get_name()
            plt.rcParams['axes.unicode_minus'] = False
        except Exception as e:
            logger.warning(f"차트 폰트 설정 실패: {e}")

    # 1x2 서브플롯 생성 (좌우 배치)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 3.5))
    fig.patch.set_facecolor('#f8fafc')
    
    # === 왼쪽: 활동 수 원형 게이지 차트 ===
    max_activities = 15  # 목표 활동 수
    activity_ratio = min(total_activities / max_activities, 1.0)
    
    # 도넛 차트 생성
    colors_donut = ['#6366f1', '#e5e7eb']
    sizes = [activity_ratio * 100, (1 - activity_ratio) * 100]
    
    wedges, texts = ax1.pie(sizes, colors=colors_donut, startangle=90,
                             counterclock=False, wedgeprops=dict(width=0.4))
    
    # 중앙에 숫자 표시
    ax1.text(0, 0, f'{total_activities}', 
             ha='center', va='center', fontsize=24, fontweight='bold', color='#1f2937')
    ax1.text(0, -0.25, '총 활동 수', 
             ha='center', va='center', fontsize=10, color='#6b7280')
    ax1.text(0, -0.45, f'(목표: {max_activities}개)', 
             ha='center', va='center', fontsize=9, color='#9ca3af')
    
    ax1.set_title('활동 참여도', fontsize=12, fontweight='bold', pad=10, color='#1f2937')
    
    # === 오른쪽: 통계 카드 스타일 ===
    ax2.axis('off')  # 축 제거
    
    # 배경 박스들
    from matplotlib.patches import FancyBboxPatch
    
    # 활동 시간 카드
    card1 = FancyBboxPatch((0.05, 0.55), 0.9, 0.35, 
                           boxstyle="round,pad=0.05", 
                           facecolor='#10b981', edgecolor='none', alpha=0.15)
    ax2.add_patch(card1)
    
    # 평균 시간 카드
    card2 = FancyBboxPatch((0.05, 0.1), 0.9, 0.35, 
                           boxstyle="round,pad=0.05", 
                           facecolor='#f59e0b', edgecolor='none', alpha=0.15)
    ax2.add_patch(card2)
    
    # 텍스트 추가
    avg_hours = total_hours / total_activities if total_activities > 0 else 0
    
    # 총 활동 시간
    ax2.text(0.5, 0.8, f'{total_hours:.1f}시간', 
             ha='center', va='center', fontsize=18, fontweight='bold', 
             color='#10b981', transform=ax2.transAxes)
    ax2.text(0.5, 0.65, '총 활동 시간', 
             ha='center', va='center', fontsize=10, color='#6b7280',
             transform=ax2.transAxes)
    
    # 평균 활동 시간
    ax2.text(0.5, 0.35, f'{avg_hours:.1f}시간', 
             ha='center', va='center', fontsize=18, fontweight='bold', 
             color='#f59e0b', transform=ax2.transAxes)
    ax2.text(0.5, 0.2, '평균 활동 시간', 
             ha='center', va='center', fontsize=10, color='#6b7280',
             transform=ax2.transAxes)
    
    ax2.set_xlim(0, 1)
    ax2.set_ylim(0, 1)
    ax2.set_title('활동 시간 분석', fontsize=12, fontweight='bold', pad=10, color='#1f2937')
    
    # 전체 레이아웃 조정
    plt.tight_layout(pad=2)

    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', bbox_inches='tight', dpi=120, 
                facecolor='#f8fafc', edgecolor='none')
    plt.close(fig)
    buffer.seek(0)
    return buffer

# 개선된 색상 팔레트
HEADER_COLOR = colors.HexColor('#1f2937')
ACCENT_COLOR = colors.HexColor('#3b82f6')
BG_LIGHT = colors.HexColor('#f7f7f9')
BORDER_COLOR = colors.HexColor('#e5e7eb')

def create_report_pdf_bytes(report: UserReport) -> bytes:
    font_registered, font_path = register_korean_fonts()
    font_name = 'NotoSansKR-Regular' if font_registered else 'Helvetica'
    font_name_bold = 'NotoSansKR-Bold' if font_registered else 'Helvetica-Bold'
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, 
                          topMargin=2.5*cm, bottomMargin=2*cm)
    
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=24,
        spaceAfter=15,
        alignment=TA_CENTER,
        textColor=HEADER_COLOR,
        fontName=font_name_bold
    )
    
    header_style = ParagraphStyle(
        'Header',
        parent=styles['Heading2'],
        fontSize=15,
        spaceAfter=10,
        spaceBefore=25,
        textColor=ACCENT_COLOR,
        fontName=font_name_bold
    )
    
    normal_style = ParagraphStyle(
        'Normal',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=6,
        leading=16,
        alignment=TA_LEFT,
        fontName=font_name 
    )
    
    bold_style = ParagraphStyle(
        'Bold',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=6,
        leading=16,
        alignment=TA_LEFT,
        fontName=font_name_bold
    )

    story = []
    
    # 제목
    story.append(Paragraph("비교과 활동 리포트", title_style))
    story.append(Paragraph(
        f"사용자: {report.user_name} | 리포트 기간: {report.start_date.strftime('%Y-%m-%d')} ~ {report.end_date.strftime('%Y-%m-%d')}", 
        ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=11, 
                      alignment=TA_CENTER, spaceAfter=25, fontName=font_name, 
                      textColor=HEADER_COLOR)
    ))
    
    # 활동 통계 차트
    story.append(Paragraph("☀ 활동 통계 대시보드", header_style))
    story.append(Spacer(1, 0.3*cm))
    
    try:
        chart_buffer = generate_activity_bar_chart_buffer(report.stats, font_path)
        # 이미지 크기를 페이지에 맞게 제한
        img = Image(chart_buffer, width=15*cm, height=6*cm)
        # 중앙 정렬
        story.append(Table([[img]], colWidths=[15*cm], 
                          style=TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER')])))
        story.append(Spacer(1, 0.8*cm))
    except Exception as e:
        logger.error(f"시각화 생성 실패: {e}")
        story.append(Paragraph("시각화 생성에 실패했습니다.", normal_style))
        story.append(Spacer(1, 0.4*cm))

    # 핵심 요약 표
    story.append(Paragraph("◆ 핵심 지표", header_style))

    stats = report.stats
    total_activities = getattr(stats, 'total_activities', 0)
    total_hours = getattr(stats, 'total_hours', 0.0)
    
    stats_data = [
        ['총 활동 수', f"{total_activities}개"],
        ['총 활동 시간', f"{total_hours:.1f}시간"],
        ['활동 수준', get_activity_level(total_activities)],
    ]
    
    stats_table = Table(stats_data, colWidths=[5*cm, 10*cm])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), BG_LIGHT),
        ('TEXTCOLOR', (0, 0), (-1, -1), HEADER_COLOR),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), font_name_bold),
        ('FONTNAME', (1, 0), (1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    
    story.append(stats_table)
    story.append(Spacer(1, 0.8*cm))

    # 인사이트
    story.append(Paragraph("☁ 인사이트", header_style))
    insights = report.insights or []
    if insights:
        for insight in insights:
            story.append(Paragraph(f"• {insight}", normal_style))
    else:
        story.append(Paragraph("특별한 인사이트가 없습니다.", normal_style))
    
    story.append(Spacer(1, 0.5*cm))
    
    # 추천사항
    story.append(Paragraph("★ 추천 활동", header_style))
    recommendations = report.recommendations or []
    if recommendations:
        for rec in recommendations:
            story.append(Paragraph(f"• {rec}", normal_style))
    else:
        story.append(Paragraph("추천할 활동이 없습니다.", normal_style))
    
    story.append(Spacer(1, 0.5*cm))
    
    # 피드백
    story.append(Paragraph("◇ 상세 피드백", header_style))
    feedback = report.feedback_message or ''
    if feedback:
        for para in feedback.split('\n'):
            if para.strip():
                story.append(Paragraph(para.strip(), normal_style))
    else:
        story.append(Paragraph("피드백이 없습니다.", normal_style))
    
    # 푸터
    story.append(Spacer(1, 1.5*cm))
    created_str = report.created_at.strftime('%Y-%m-%d %H:%M') if hasattr(report, 'created_at') and report.created_at else datetime.now().strftime('%Y-%m-%d %H:%M')

    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=9,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#6b7280'),
        fontName=font_name
    )
    story.append(Paragraph(f"리포트 생성 일시: {created_str} | © 건국대학교 비교과센터", 
                          footer_style))
    
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

def get_activity_level(count: int) -> str:
    """활동 수준 판단 - 유니코드 심볼 사용"""
    if count == 0:
        return "● 활동 없음"
    elif count < 3:
        return "◐ 낮음"
    elif count < 8:
        return "○ 보통"
    else:
        return "◉ 높음"