from datetime import datetime
from app.models.activity import UserReport
import io
import os
import logging
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

logger = logging.getLogger(__name__)

def register_korean_fonts():
    try:
        # 폰트 파일 경로
        base_path = os.path.join(os.path.dirname(__file__), '..', 'utils', 'format', 'fonts')
        regular_font_path = os.path.join(base_path, 'NotoSansKR-Regular.ttf')
        bold_font_path = os.path.join(base_path, 'NotoSansKR-Bold.ttf')
        
        # 폰트 등록
        pdfmetrics.registerFont(TTFont('NotoSansKR-Regular', regular_font_path))
        pdfmetrics.registerFont(TTFont('NotoSansKR-Bold', bold_font_path))
        
        # 폰트 패밀리 등록
        from reportlab.pdfbase.pdfmetrics import registerFontFamily
        registerFontFamily('NotoSansKR',
                         normal='NotoSansKR-Regular',
                         bold='NotoSansKR-Bold')
        
        logger.info("한글 폰트 등록 완료")
        return True
        
    except Exception as e:
        logger.error(f"폰트 등록 실패: {e}")
        # 폰트 등록 실패시 기본 폰트 사용
        return False

def create_report_pdf_bytes(report: UserReport) -> bytes:
    # 한글 폰트 등록
    font_registered = register_korean_fonts()
    font_name = 'NotoSansKR-Regular' if font_registered else 'Helvetica'
    font_name_bold = 'NotoSansKR-Bold' if font_registered else 'Helvetica-Bold'
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    
    # 스타일 정의
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=20,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#1f2937'),
        fontName=font_name_bold
    )
    
    header_style = ParagraphStyle(
        'Header',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=15,
        spaceBefore=20,
        textColor=colors.HexColor('#374151'),
        fontName=font_name_bold
    )
    
    normal_style = ParagraphStyle(
        'Normal',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=8,
        leading=14,
        fontName=font_name
    )
    
    # PDF 컨텐츠 생성
    story = []
    
    # 제목
    story.append(Paragraph("비교과 활동 리포트", title_style))
    
    # 메타 정보
    start_date_str = report.start_date.strftime('%Y-%m-%d') if report.start_date else "시작일 없음"
    end_date_str = report.end_date.strftime('%Y-%m-%d') if report.end_date else "종료일 없음"
    created_str = report.created_at.strftime('%Y-%m-%d %H:%M') if hasattr(report, 'created_at') and report.created_at else datetime.now().strftime('%Y-%m-%d %H:%M')
    
    meta_data = [
        ['사용자 이름', str(report.user_name)],
        ['리포트 기간', f"{start_date_str} ~ {end_date_str}"],
        ['생성 일시', created_str],
    ]
    
    meta_table = Table(meta_data, colWidths=[4*cm, 8*cm])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f3f4f6')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#374151')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), font_name_bold),
        ('FONTNAME', (1, 0), (1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#d1d5db')),
    ]))
    
    story.append(meta_table)
    story.append(Spacer(1, 0.5*cm))
    
    # 활동 통계
    story.append(Paragraph("■ 활동 통계", header_style))
    
    stats = report.stats
    total_activities = getattr(stats, 'total_activities', 0)
    total_hours = getattr(stats, 'total_hours', 0.0)
    
    stats_data = [
        ['총 활동 수', f"{total_activities}개"],
        ['총 활동 시간', f"{total_hours:.1f}시간"],
        ['활동 수준', get_activity_level(total_activities)],
    ]
    
    stats_table = Table(stats_data, colWidths=[4*cm, 8*cm])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#eff6ff')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1f2937')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), font_name_bold),
        ('FONTNAME', (1, 0), (1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#d1d5db')),
    ]))
    
    story.append(stats_table)
    story.append(Spacer(1, 0.4*cm))
    
    # 인사이트
    story.append(Paragraph("■ 인사이트", header_style))
    insights = report.insights or []
    if insights:
        for i, insight in enumerate(insights, 1):
            story.append(Paragraph(f"{i}. {insight}", normal_style))
    else:
        story.append(Paragraph("이번 기간에는 특별한 인사이트가 없습니다.", normal_style))
    
    story.append(Spacer(1, 0.3*cm))
    
    # 추천사항
    story.append(Paragraph("■ 추천사항", header_style))
    recommendations = report.recommendations or []
    if recommendations:
        for i, rec in enumerate(recommendations, 1):
            story.append(Paragraph(f"{i}. {rec}", normal_style))
    else:
        story.append(Paragraph("현재 추천할 활동이 없습니다.", normal_style))
    
    story.append(Spacer(1, 0.3*cm))
    
    # 피드백 메시지
    story.append(Paragraph("■ 상세 피드백", header_style))
    feedback = report.feedback_message or ''
    if feedback:
        # 긴 텍스트는 여러 단락으로 나누기
        feedback_paragraphs = feedback.split('\n')
        for para in feedback_paragraphs:
            if para.strip():
                story.append(Paragraph(para.strip(), normal_style))
    else:
        story.append(Paragraph("피드백이 없습니다.", normal_style))
    
    # 푸터
    story.append(Spacer(1, 1*cm))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#6b7280'),
        fontName=font_name
    )
    story.append(Paragraph("© 건국대학교 비교과센터 | 문의: pyeonk@konkuk.ac.kr", footer_style))
    
    # PDF 생성
    doc.build(story)
    
    # bytes 반환
    buffer.seek(0)
    return buffer.getvalue()

def get_activity_level(count: int) -> str:
    """활동 수준 판단"""
    if count == 0:
        return "■ 활동 없음"
    elif count < 3:
        return "■ 낮음"  
    elif count < 8:
        return "■ 보통"
    else:
        return "■ 높음"