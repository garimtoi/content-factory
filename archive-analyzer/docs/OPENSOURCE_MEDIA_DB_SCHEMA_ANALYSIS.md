# 오픈소스 미디어 관리 솔루션 DB 스키마 비교 분석

**작성일**: 2025-12-03
**대상**: Jellyfin, Plex, Kodi, MediaCMS, PeerTube
**목적**: Archive Analyzer 스키마 설계를 위한 오픈소스 미디어 플랫폼 DB 구조 분석

---

## 1. Executive Summary

### 라이선스별 분류

| 솔루션 | 라이선스 | DB 엔진 | 아키텍처 | 오픈소스 |
|--------|---------|---------|---------|---------|
| **Jellyfin** | GPL-2.0 | SQLite → PostgreSQL 전환 중 | EFCore ORM | ✅ 완전 오픈소스 |
| **Plex** | Proprietary | SQLite | Custom ORM | ❌ 상용 (스키마 미공개) |
| **Kodi** | GPL-2.0 | SQLite/MySQL | Raw SQL | ✅ 완전 오픈소스 |
| **MediaCMS** | AGPL-3.0 | PostgreSQL | Django ORM | ✅ 완전 오픈소스 |
| **PeerTube** | AGPL-3.0 | PostgreSQL | Sequelize ORM | ✅ 완전 오픈소스 |

### 권장 참고 순서 (MIT/Apache 우선 → GPL/AGPL)

1. **Kodi** (GPL-2.0): 가장 성숙한 미디어 라이브러리 스키마, 30개 테이블 + 6개 뷰
2. **Jellyfin** (GPL-2.0): 모던 EFCore 마이그레이션 진행 중, PostgreSQL 지원 예정
3. **MediaCMS** (AGPL-3.0): Django 기반 클린 아키텍처, 카테고리/태그/플레이리스트
4. **PeerTube** (AGPL-3.0): 연합형 비디오 플랫폼, ActivityPub 통합

**참고**: MIT/Apache 라이선스 전용 미디어 DB 스키마는 발견되지 않음.
**TagLib#** (LGPL-2.1)는 메타데이터 추출 라이브러리이나 DB 스키마 제공 없음.

---

## 2. Kodi (XBMC) MyVideos Database

**라이선스**: GPL-2.0
**DB**: SQLite/MySQL 선택 가능
**버전**: v17.6 기준 (30 tables + 6 views)

### 2.1 핵심 테이블 구조

#### 미디어 계층 (Media Hierarchy)

```sql
-- 영화
CREATE TABLE movie (
    idMovie INTEGER PRIMARY KEY,
    c00 TEXT,  -- title
    c01 TEXT,  -- plot
    c07 TEXT,  -- year
    c14 TEXT,  -- genre
    c23 TEXT,  -- path
    -- c00~c23: 24개 메타데이터 컬럼
);

-- TV 쇼 계층: tvshow → seasons → episode
CREATE TABLE tvshow (
    idShow INTEGER PRIMARY KEY,
    c00 TEXT,  -- title
    c01 TEXT,  -- plot
    -- ...
);

CREATE TABLE seasons (
    idSeason INTEGER PRIMARY KEY,
    idShow INTEGER,
    season INTEGER,
    FOREIGN KEY(idShow) REFERENCES tvshow(idShow)
);

CREATE TABLE episode (
    idEpisode INTEGER PRIMARY KEY,
    c00 TEXT,  -- title
    c12 TEXT,  -- season
    c13 TEXT,  -- episode number
    idShow INTEGER,
    FOREIGN KEY(idShow) REFERENCES tvshow(idShow)
);

-- TV 쇼 ↔ 에피소드 링크
CREATE TABLE tvshowlinkepisode (
    idShow INTEGER,
    idEpisode INTEGER,
    PRIMARY KEY(idEpisode, idShow)
);

-- 뮤직비디오
CREATE TABLE musicvideo (
    idMVideo INTEGER PRIMARY KEY,
    c00 TEXT,  -- title
    c04 TEXT,  -- director
    -- ...
);
```

#### 관계 테이블 (N:N Many-to-Many Links)

```sql
-- 배우/출연진 링크 (공통)
CREATE TABLE actor (
    actor_id INTEGER PRIMARY KEY,
    name TEXT,
    art_urls TEXT
);

CREATE TABLE actor_link (
    actor_id INTEGER,
    media_id INTEGER,
    media_type TEXT,  -- 'movie', 'tvshow', 'episode', 'musicvideo'
    role TEXT,
    cast_order INTEGER
);

-- 장르 링크
CREATE TABLE genre_link (
    genre_id INTEGER,
    media_id INTEGER,
    media_type TEXT,
    UNIQUE KEY(genre_id, media_type, media_id)
);

-- 태그 링크
CREATE TABLE tag_link (
    tag_id INTEGER,
    media_id INTEGER,
    media_type TEXT,
    UNIQUE KEY(tag_id, media_type, media_id)
);

-- 감독/작가 링크
CREATE TABLE director_link (
    actor_id INTEGER,
    media_id INTEGER,
    media_type TEXT
);

CREATE TABLE writer_link (
    actor_id INTEGER,
    media_id INTEGER,
    media_type TEXT
);

-- 제작사/국가 링크
CREATE TABLE studio_link (
    studio_id INTEGER,
    media_id INTEGER,
    media_type TEXT
);

CREATE TABLE country_link (
    country_id INTEGER,
    media_id INTEGER,
    media_type TEXT
);
```

#### 메타데이터 & 파일 관리

```sql
-- 평점 (다중 소스)
CREATE TABLE rating (
    rating_id INTEGER PRIMARY KEY,
    media_id INTEGER,
    media_type TEXT,
    rating_type TEXT,  -- 'default', 'imdb', 'tmdb'
    rating FLOAT,
    votes INTEGER
);

-- 외부 ID (IMDb, TMDb 등)
CREATE TABLE uniqueid (
    uniqueid_id INTEGER PRIMARY KEY,
    media_id INTEGER,
    media_type TEXT,
    value TEXT,  -- 'tt1234567'
    type TEXT    -- 'imdb', 'tmdb', 'tvdb'
);

-- 아트워크 (포스터, 팬아트 등)
CREATE TABLE art (
    art_id INTEGER PRIMARY KEY,
    media_id INTEGER,
    media_type TEXT,
    type TEXT,  -- 'poster', 'fanart', 'banner', 'thumb'
    url TEXT
);

-- 파일 정보
CREATE TABLE files (
    idFile INTEGER PRIMARY KEY,
    idPath INTEGER,
    strFilename TEXT,
    playCount INTEGER,
    lastPlayed TEXT,
    dateAdded TEXT,
    FOREIGN KEY(idPath) REFERENCES path(idPath)
);

CREATE TABLE path (
    idPath INTEGER PRIMARY KEY,
    strPath TEXT,
    strContent TEXT,  -- 'movies', 'tvshows', 'musicvideos'
    strScraper TEXT
);

-- 북마크 (재생 위치)
CREATE TABLE bookmark (
    idBookmark INTEGER PRIMARY KEY,
    idFile INTEGER,
    timeInSeconds DOUBLE,
    type INTEGER  -- 0=resume point, 1=chapter
);

-- 영화 컬렉션 (시리즈)
CREATE TABLE sets (
    idSet INTEGER PRIMARY KEY,
    strSet TEXT,  -- 'The Lord of the Rings'
    strOverview TEXT
);

CREATE TABLE movie_sets (
    idMovie INTEGER,
    idSet INTEGER
);
```

#### Views (조인 편의성)

```sql
-- 영화 뷰 (movie + file + path 조인)
CREATE VIEW movie_view AS
SELECT
    m.*,
    f.strFilename,
    p.strPath
FROM movie m
JOIN files f ON m.idFile = f.idFile
JOIN path p ON f.idPath = p.idPath;

-- 에피소드 뷰 (episode + file + tvshow 조인)
CREATE VIEW episode_view AS
SELECT
    e.*,
    f.strFilename,
    t.c00 AS tvshow_title
FROM episode e
JOIN files f ON e.idFile = f.idFile
JOIN tvshowlinkepisode tl ON e.idEpisode = tl.idEpisode
JOIN tvshow t ON tl.idShow = t.idShow;
```

### 2.2 트리거 (Cascading Delete)

```sql
-- 영화 삭제 시 관련 링크 자동 삭제
CREATE TRIGGER delete_movie
AFTER DELETE ON movie
FOR EACH ROW
BEGIN
    DELETE FROM genre_link WHERE media_id=old.idMovie AND media_type='movie';
    DELETE FROM actor_link WHERE media_id=old.idMovie AND media_type='movie';
    DELETE FROM tag_link WHERE media_id=old.idMovie AND media_type='movie';
    DELETE FROM director_link WHERE media_id=old.idMovie AND media_type='movie';
    DELETE FROM writer_link WHERE media_id=old.idMovie AND media_type='movie';
    DELETE FROM studio_link WHERE media_id=old.idMovie AND media_type='movie';
END;
```

### 2.3 설계 특징

| 특징 | 구현 방식 |
|------|---------|
| **다형성 (Polymorphic)** | `media_type` TEXT 컬럼으로 movie/tvshow/episode/musicvideo 구분 |
| **메타데이터 저장** | `c00~c23` 고정 컬럼 (유연성 낮음, 성능 높음) |
| **계층 구조** | tvshow → seasons → episode (3단 계층) |
| **N:N 관계** | 모든 링크 테이블에 복합키 사용 |
| **외부 ID** | uniqueid 테이블로 다중 스크래퍼 지원 |
| **평점** | rating 테이블로 IMDb/TMDb 등 다중 소스 |
| **재생 추적** | files.playCount, bookmark.timeInSeconds |

**장점**:
- 성숙한 스키마 (15년+ 검증)
- MySQL 공유 DB 지원 → 다중 클라이언트 동기화
- 뷰(View)로 복잡한 조인 단순화

**단점**:
- `c00~c23` 컬럼명이 직관적이지 않음
- 스키마 변경 어려움 (고정 컬럼)
- BLOB 메타데이터 미지원 (JSON 등)

---

## 3. Jellyfin

**라이선스**: GPL-2.0
**DB**: SQLite (현재) → PostgreSQL/MySQL 마이그레이션 예정
**ORM**: Entity Framework Core (EFCore)

### 3.1 현재 상태 (2025년 기준)

#### 데이터베이스 구조
- `jellyfin.db`: 메인 DB (사용자, 인증, 활동 로그)
- `library.db`: 미디어 라이브러리 (EFCore 마이그레이션 진행 중)

```
Jellyfin.Data/Entities/
├── User.cs                 # 사용자
├── Activity.cs             # 활동 로그
├── DisplayPreferences.cs   # 표시 설정
└── (library 엔티티 마이그레이션 중)

Jellyfin.Server.Implementations/Migrations/
├── 20210101_CreateUserTable.cs
├── 20210102_CreateActivityTable.cs
└── (진행 중)
```

#### 핵심 테이블 (EFCore)

```csharp
// User 엔티티 (jellyfin.db)
public class User
{
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public Guid Id { get; set; }

    public string Username { get; set; }
    public string Password { get; set; }
    public DateTime CreatedDate { get; set; }

    // Navigation properties
    public ICollection<UserData> UserDatas { get; set; }
    public ICollection<AccessSchedule> AccessSchedules { get; set; }
}

// UserData: 재생 상태 추적
public class UserData
{
    public Guid UserId { get; set; }
    public Guid ItemId { get; set; }
    public string CustomDataKey { get; set; }  // 복합키

    public long PlaybackPositionTicks { get; set; }
    public int PlayCount { get; set; }
    public bool IsFavorite { get; set; }
    public DateTime LastPlayedDate { get; set; }

    [ForeignKey(nameof(UserId))]
    public User User { get; set; }
}

// Activity 로그
public class Activity
{
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int Id { get; set; }

    public string Name { get; set; }
    public string Overview { get; set; }
    public string Type { get; set; }
    public Guid UserId { get; set; }
    public DateTime DateCreated { get; set; }

    [ForeignKey(nameof(UserId))]
    public User User { get; set; }
}
```

#### Library.db 마이그레이션 (진행 중)

```sql
-- 기존: Raw SQL + XML 메타데이터 혼용
-- 목표: EFCore 엔티티로 통합

-- TypedBaseItems 테이블 (현재)
CREATE TABLE TypedBaseItems (
    guid TEXT PRIMARY KEY,
    type TEXT,
    data BLOB,  -- XML 직렬화 메타데이터
    -- ...
);

-- mediastreams 테이블 (현재)
CREATE TABLE mediastreams (
    Id INTEGER PRIMARY KEY,
    ItemId TEXT,
    StreamIndex INTEGER,
    StreamType INTEGER,  -- 0=Audio, 1=Video, 2=Subtitle
    Codec TEXT,
    Language TEXT,
    -- ...
);
```

#### 마이그레이션 목표 (PR #12798)

```csharp
// 새로운 BaseItem 엔티티 (EFCore)
public abstract class BaseItem
{
    [Key]
    public Guid Id { get; set; }

    public string Name { get; set; }
    public string Path { get; set; }
    public DateTime DateCreated { get; set; }
    public DateTime DateModified { get; set; }

    // 계층 구조
    public Guid? ParentId { get; set; }
    [ForeignKey(nameof(ParentId))]
    public virtual BaseItem Parent { get; set; }

    public virtual ICollection<BaseItem> Children { get; set; }

    // 메타데이터
    public string Overview { get; set; }
    public int? ProductionYear { get; set; }

    // Navigation properties
    public virtual ICollection<ItemGenre> Genres { get; set; }
    public virtual ICollection<ItemTag> Tags { get; set; }
    public virtual ICollection<ItemPerson> People { get; set; }
}

// 영화
public class Movie : BaseItem
{
    public string Tagline { get; set; }
    public int? Budget { get; set; }
    public int? Revenue { get; set; }
}

// TV 시리즈
public class Series : BaseItem
{
    public SeriesStatus Status { get; set; }
    public DateTime? PremiereDate { get; set; }
}

// 에피소드
public class Episode : BaseItem
{
    public int? SeasonNumber { get; set; }
    public int? EpisodeNumber { get; set; }

    public Guid SeriesId { get; set; }
    [ForeignKey(nameof(SeriesId))]
    public virtual Series Series { get; set; }
}

// N:N 관계 (Join 테이블)
public class ItemGenre
{
    public Guid ItemId { get; set; }
    public int GenreId { get; set; }

    [ForeignKey(nameof(ItemId))]
    public virtual BaseItem Item { get; set; }

    [ForeignKey(nameof(GenreId))]
    public virtual Genre Genre { get; set; }
}

public class ItemPerson
{
    public Guid ItemId { get; set; }
    public int PersonId { get; set; }
    public PersonKind Type { get; set; }  // Actor, Director, Writer
    public string Role { get; set; }
    public int SortOrder { get; set; }

    [ForeignKey(nameof(ItemId))]
    public virtual BaseItem Item { get; set; }

    [ForeignKey(nameof(PersonId))]
    public virtual Person Person { get; set; }
}
```

### 3.2 설계 철학

1. **타입 안전성**: C# 강타입 엔티티 (JSON BLOB 지양)
2. **외부 DB 지원**: PostgreSQL/MySQL 마이그레이션 목표
3. **추상 계층**: BaseItem 상속으로 Movie/Series/Episode 확장
4. **복합키 회피**: GUID Primary Key 사용
5. **Navigation Properties**: EFCore lazy/eager loading

### 3.3 장단점

**장점**:
- 모던 ORM (EFCore) → 타입 안전성
- PostgreSQL 지원 예정 → 로드밸런싱/페일오버
- 계층 구조 (ParentId) → 무한 중첩 가능

**단점**:
- 마이그레이션 미완료 (2025년 진행 중)
- 기존 library.db는 XML BLOB 사용 (레거시)

---

## 4. MediaCMS

**라이선스**: AGPL-3.0
**DB**: PostgreSQL
**ORM**: Django ORM
**언어**: Python 3.11

### 4.1 모델 구조

```
files/models/
├── media.py        # 핵심 미디어 모델
├── category.py     # 카테고리
├── tag.py          # (추정)
├── encoding.py     # 인코딩 프로파일
├── comment.py      # 댓글
├── rating.py       # 평점
├── playlist.py     # 플레이리스트
├── subtitle.py     # 자막
├── license.py      # 라이선스
├── page.py         # CMS 페이지
└── video_data.py   # 비디오별 메타데이터
```

#### 핵심 모델 (Django ORM)

```python
# files/models/media.py
class Media(models.Model):
    """핵심 미디어 엔티티"""

    # 기본 필드
    uid = models.UUIDField(default=uuid.uuid4, unique=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    # 미디어 타입
    MEDIA_TYPE_CHOICES = [
        ('video', 'Video'),
        ('audio', 'Audio'),
        ('image', 'Image'),
        ('pdf', 'PDF'),
    ]
    media_type = models.CharField(max_length=20, choices=MEDIA_TYPE_CHOICES)

    # 파일 정보
    media_file = models.FileField(upload_to='media/')
    size = models.BigIntegerField(default=0)
    duration = models.IntegerField(null=True, blank=True)  # seconds

    # 상태 관리
    STATE_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('ready', 'Ready'),
        ('error', 'Error'),
    ]
    state = models.CharField(max_length=20, choices=STATE_CHOICES, default='pending')
    encoding_status = models.CharField(max_length=100, blank=True)

    # 퍼블리싱 워크플로우
    is_published = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    is_reviewed = models.BooleanField(default=False)

    # 사용자 & 권한
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='media_items')

    # 분류 (N:N)
    categories = models.ManyToManyField('Category', related_name='media_items', blank=True)
    tags = models.ManyToManyField('Tag', related_name='media_items', blank=True)

    # 통계
    views = models.IntegerField(default=0)
    likes = models.IntegerField(default=0)

    # 타임스탬프
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['state', 'media_type']),
            models.Index(fields=['user', 'is_published']),
        ]

# files/models/category.py
class Category(models.Model):
    """RBAC 카테고리"""
    title = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    # 계층 구조 (선택)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE)

    # 권한 그룹
    view_groups = models.ManyToManyField(Group, related_name='viewable_categories', blank=True)
    edit_groups = models.ManyToManyField(Group, related_name='editable_categories', blank=True)

# files/models/encoding.py
class Encoding(models.Model):
    """인코딩 프로파일 (FFmpeg)"""
    media = models.ForeignKey(Media, on_delete=models.CASCADE, related_name='encodings')

    # 프로파일
    profile = models.CharField(max_length=50)  # '1080p-h264', '720p-vp9'
    codec = models.CharField(max_length=20)    # 'h264', 'h265', 'vp9'
    resolution = models.CharField(max_length=20)  # '1920x1080', '1280x720'

    # 출력 파일
    encoded_file = models.FileField(upload_to='encoded/', null=True)
    size = models.BigIntegerField(default=0)

    # 상태
    status = models.CharField(max_length=20, default='pending')  # pending, processing, completed, failed
    progress = models.IntegerField(default=0)  # 0-100

    created_at = models.DateTimeField(auto_now_add=True)

# files/models/playlist.py
class Playlist(models.Model):
    """플레이리스트"""
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    # 미디어 N:N (순서 보존)
    media_items = models.ManyToManyField(Media, through='PlaylistItem')

    is_public = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

class PlaylistItem(models.Model):
    """플레이리스트 아이템 (순서 관리)"""
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE)
    media = models.ForeignKey(Media, on_delete=models.CASCADE)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']
        unique_together = ['playlist', 'media']

# files/models/comment.py
class Comment(models.Model):
    """사용자 댓글"""
    media = models.ForeignKey(Media, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()

    # 계층 구조 (대댓글)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='replies')

    created_at = models.DateTimeField(auto_now_add=True)

# files/models/subtitle.py
class Subtitle(models.Model):
    """자막 파일"""
    media = models.ForeignKey(Media, on_delete=models.CASCADE, related_name='subtitles')
    language = models.CharField(max_length=10)  # 'en', 'ko', 'ja'
    subtitle_file = models.FileField(upload_to='subtitles/')

    # WebVTT, SRT 등
    format = models.CharField(max_length=10, default='vtt')
```

### 4.2 설계 특징

| 특징 | 구현 방식 |
|------|---------|
| **퍼블리싱 워크플로우** | `state`, `is_published`, `is_reviewed` 플래그 |
| **다중 인코딩** | Encoding 모델 (1:N), 7개 기본 프로파일 (144p~2160p) |
| **RBAC** | Category.view_groups / edit_groups |
| **통계 추적** | views, likes 필드 (비정규화) |
| **플레이리스트 순서** | Through 모델 (PlaylistItem.order) |
| **댓글 계층** | Comment.parent (self-referencing FK) |

### 4.3 장단점

**장점**:
- Django Admin 자동 생성 → 빠른 프로토타이핑
- PostgreSQL → 풀텍스트 검색, JSON 필드 지원
- AGPL → 소스 공개 의무 (오픈소스 보증)

**단점**:
- AGPL 라이선스 → 상용 제품 통합 시 전체 공개 의무
- ORM 성능 (N+1 쿼리 주의)

---

## 5. PeerTube

**라이선스**: AGPL-3.0
**DB**: PostgreSQL
**ORM**: Sequelize (Node.js)
**아키텍처**: ActivityPub 연합형

### 5.1 모델 구조

```
server/core/models/
├── video/
│   ├── video.ts                      # 핵심 비디오 모델
│   ├── video-file.ts                 # 파일/해상도별 인코딩
│   ├── video-channel.ts              # 채널 (소유권)
│   ├── tag.ts & video-tag.ts         # 태그 (N:N)
│   ├── video-caption.ts              # 자막
│   ├── video-chapter.ts              # 챕터
│   ├── video-playlist.ts             # 플레이리스트
│   ├── video-streaming-playlist.ts   # HLS/DASH
│   ├── video-live.ts                 # 라이브 스트리밍
│   ├── video-comment.ts              # 댓글
│   ├── video-blacklist.ts            # 모더레이션
│   └── thumbnail.ts                  # 썸네일
├── account/
│   └── account.ts                    # 계정
└── actor/
    └── actor.ts                      # ActivityPub Actor
```

#### 핵심 모델 (Sequelize)

```typescript
// server/core/models/video/video.ts
@Scopes(() => ({
  // ...복잡한 스코프 정의
}))
@Table({
  tableName: 'video',
  indexes: [
    { fields: ['name'] },
    { fields: ['createdAt'] },
    { fields: ['duration'] },
    { fields: ['views'] },
    { fields: ['channelId'] }
  ]
})
export class VideoModel extends Model<Partial<AttributesOnly<VideoModel>>> {
  @AllowNull(false)
  @Default(DataType.UUIDV4)
  @IsUUID(4)
  @Column(DataType.UUID)
  uuid: string

  @AllowNull(false)
  @Is('VideoName', value => throwIfNotValid(value, isVideoNameValid, 'name'))
  @Column
  name: string

  @AllowNull(true)
  @Is('VideoDescription', value => throwIfNotValid(value, isVideoDescriptionValid, 'description', true))
  @Column(DataType.STRING(CONSTRAINTS_FIELDS.VIDEOS.DESCRIPTION.max))
  description: string

  @AllowNull(false)
  @Column
  duration: number  // seconds

  @AllowNull(false)
  @Default(0)
  @Column
  views: number

  @AllowNull(false)
  @Default(0)
  @Column
  likes: number

  @AllowNull(false)
  @Default(0)
  @Column
  dislikes: number

  // 상태
  @AllowNull(false)
  @Default(VideoState.PUBLISHED)
  @Column
  state: VideoState  // PUBLISHED, TO_TRANSCODE, TO_IMPORT, etc.

  // 프라이버시
  @AllowNull(false)
  @Default(VideoPrivacy.PRIVATE)
  @Column
  privacy: VideoPrivacy  // PUBLIC, UNLISTED, PRIVATE, INTERNAL

  // 채널 (소유권)
  @ForeignKey(() => VideoChannelModel)
  @Column
  channelId: number

  @BelongsTo(() => VideoChannelModel, {
    foreignKey: { allowNull: true },
    onDelete: 'cascade'
  })
  VideoChannel: VideoChannelModel

  // N:N 관계
  @BelongsToMany(() => TagModel, {
    through: () => VideoTagModel,
    onDelete: 'CASCADE'
  })
  Tags: TagModel[]

  // 1:N 관계
  @HasMany(() => VideoFileModel, { onDelete: 'cascade' })
  VideoFiles: VideoFileModel[]

  @HasMany(() => VideoCaptionModel, { onDelete: 'cascade' })
  VideoCaptions: VideoCaptionModel[]

  @HasMany(() => VideoCommentModel, { onDelete: 'cascade' })
  VideoComments: VideoCommentModel[]

  // ActivityPub
  @AllowNull(false)
  @Column
  url: string  // 연합형 URL (https://instance.com/videos/watch/uuid)

  @CreatedAt
  createdAt: Date

  @UpdatedAt
  updatedAt: Date
}

// server/core/models/video/video-file.ts
@Table({
  tableName: 'videoFile',
  indexes: [
    { fields: ['videoId'] },
    { fields: ['infoHash'] }
  ]
})
export class VideoFileModel extends Model {
  @AllowNull(false)
  @Column
  resolution: number  // 1080, 720, 480, etc.

  @AllowNull(false)
  @Column
  size: number  // bytes

  @AllowNull(false)
  @Column
  fps: number

  @AllowNull(true)
  @Column
  infoHash: string  // WebTorrent 해시

  @AllowNull(false)
  @Column
  codec: string  // 'h264', 'vp9'

  @ForeignKey(() => VideoModel)
  @Column
  videoId: number

  @BelongsTo(() => VideoModel, {
    foreignKey: { allowNull: true },
    onDelete: 'CASCADE'
  })
  Video: VideoModel
}

// server/core/models/video/tag.ts
@Table({
  tableName: 'tag',
  timestamps: false
})
export class TagModel extends Model {
  @AllowNull(false)
  @Column
  name: string

  @BelongsToMany(() => VideoModel, {
    through: () => VideoTagModel,
    onDelete: 'CASCADE'
  })
  Videos: VideoModel[]
}

// server/core/models/video/video-tag.ts (Join 테이블)
@Table({
  tableName: 'videoTag',
  timestamps: false,
  indexes: [
    { fields: ['videoId'] },
    { fields: ['tagId'] }
  ]
})
export class VideoTagModel extends Model {
  @ForeignKey(() => VideoModel)
  @Column
  videoId: number

  @ForeignKey(() => TagModel)
  @Column
  tagId: number
}

// server/core/models/video/video-channel.ts
@Table({
  tableName: 'videoChannel'
})
export class VideoChannelModel extends Model {
  @AllowNull(false)
  @Column
  name: string

  @AllowNull(true)
  @Column(DataType.TEXT)
  description: string

  @ForeignKey(() => AccountModel)
  @Column
  accountId: number

  @BelongsTo(() => AccountModel, {
    foreignKey: { allowNull: false },
    onDelete: 'cascade'
  })
  Account: AccountModel

  @HasMany(() => VideoModel, { onDelete: 'CASCADE' })
  Videos: VideoModel[]

  // ActivityPub
  @AllowNull(false)
  @Column
  url: string
}

// server/core/models/video/video-comment.ts
@Table({
  tableName: 'videoComment',
  indexes: [
    { fields: ['videoId'] },
    { fields: ['url'], unique: true }
  ]
})
export class VideoCommentModel extends Model {
  @AllowNull(false)
  @Column(DataType.TEXT)
  text: string

  @ForeignKey(() => VideoModel)
  @Column
  videoId: number

  @ForeignKey(() => AccountModel)
  @Column
  accountId: number

  // 계층 구조 (대댓글)
  @ForeignKey(() => VideoCommentModel)
  @Column
  inReplyToCommentId: number

  @BelongsTo(() => VideoCommentModel, {
    foreignKey: { allowNull: true },
    onDelete: 'cascade'
  })
  InReplyToVideoComment: VideoCommentModel

  // ActivityPub URL (연합형)
  @AllowNull(false)
  @Column
  url: string

  @CreatedAt
  createdAt: Date
}
```

### 5.2 설계 특징

| 특징 | 구현 방식 |
|------|---------|
| **연합형 (Federation)** | ActivityPub URL (video.url, comment.url) |
| **다중 해상도** | VideoFile 1:N (resolution, codec별) |
| **채널 소유권** | VideoChannel → Account (계층) |
| **태그 제한** | 기본 최대 5개 (설정 변경 가능) |
| **WebTorrent** | VideoFile.infoHash (P2P 배포) |
| **HLS/DASH** | VideoStreamingPlaylist (적응형 스트리밍) |
| **프라이버시** | VideoPrivacy enum (PUBLIC, UNLISTED, PRIVATE) |
| **상태 관리** | VideoState enum (PUBLISHED, TO_TRANSCODE, etc.) |
| **플러그인 확장** | 메타데이터 플러그인 (MediaInfo 통합) |

### 5.3 ActivityPub 연합형 특성

```typescript
// 연합형 URL 예시
video.url = "https://instance1.com/videos/watch/uuid-1234"
comment.url = "https://instance2.com/comments/5678"

// 다른 PeerTube 인스턴스와 메타데이터 공유
// PostgreSQL에 원격 비디오 메타데이터 복제 저장
```

### 5.4 장단점

**장점**:
- TypeScript + Sequelize → 타입 안전성
- 연합형 → 탈중앙화 비디오 플랫폼
- 플러그인 아키텍처 → MediaInfo 등 확장 가능

**단점**:
- AGPL → 상용 통합 시 소스 공개 의무
- 연합형 복잡도 → 로컬 전용 시 오버엔지니어링
- 태그 제한 (기본 5개) → 세밀한 분류 어려움

---

## 6. Plex (참고용, 상용 솔루션)

**라이선스**: Proprietary (상용)
**DB**: SQLite
**스키마**: 미공개 (역공학 필요)

### 6.1 알려진 구조 (커뮤니티 분석)

```sql
-- 주요 테이블 (추정)
-- com.plexapp.plugins.library.db

-- metadata_items: 모든 미디어 (영화, TV, 음악)
CREATE TABLE metadata_items (
    id INTEGER PRIMARY KEY,
    parent_id INTEGER,  -- 계층 구조 (show → season → episode)
    metadata_type INTEGER,  -- 1=movie, 2=show, 4=season, 5=episode
    title TEXT,
    title_sort TEXT,
    original_title TEXT,
    studio TEXT,
    rating REAL,
    year INTEGER,
    added_at INTEGER,  -- Unix timestamp
    updated_at INTEGER,
    content_rating TEXT,
    summary TEXT,
    tagline TEXT,
    -- ...
    FOREIGN KEY (parent_id) REFERENCES metadata_items(id)
);

-- media_parts: 실제 파일 경로
CREATE TABLE media_parts (
    id INTEGER PRIMARY KEY,
    media_item_id INTEGER,
    file TEXT,  -- 파일 경로
    size INTEGER,
    duration INTEGER,
    -- ...
);

-- metadata_item_views: 재생 기록
CREATE TABLE metadata_item_views (
    id INTEGER PRIMARY KEY,
    metadata_item_id INTEGER,
    view_count INTEGER,
    last_viewed_at INTEGER,
    -- ...
);

-- tags_* 테이블들 (genre, director, actor 등)
-- N:N 관계로 추정되나 정확한 스키마 미공개
```

### 6.2 특징 (추정)

- **계층 구조**: `parent_id` + `metadata_type` 조합
- **비정규화**: 성능을 위해 일부 통계 필드 중복 저장
- **커스텀 SQLite**: Plex 전용 SQLite 엔진 (표준 sqlite3 CLI 불가)

### 6.3 제약사항

- 스키마 변경 금지 (DB 손상 위험)
- 공식 문서 없음 (커뮤니티 역공학)
- 오픈소스 참고 불가 (라이선스 위반 리스크)

---

## 7. 공통 패턴 분석

### 7.1 메타데이터 저장 방식

| 솔루션 | 방식 | 장점 | 단점 |
|--------|------|------|------|
| **Kodi** | 고정 컬럼 (`c00~c23`) | 성능 우수 | 스키마 변경 어려움 |
| **Jellyfin** | 강타입 엔티티 (EFCore) | 타입 안전성 | ORM 오버헤드 |
| **MediaCMS** | Django 모델 (CharField/TextField) | 빠른 개발 | N+1 쿼리 주의 |
| **PeerTube** | Sequelize 모델 | TypeScript 통합 | 복잡한 연합형 로직 |
| **Plex** | BLOB + 비정규화 | 성능 (추정) | 스키마 미공개 |

### 7.2 계층 구조 (Hierarchy)

| 구조 | Kodi | Jellyfin | MediaCMS | PeerTube | Plex |
|------|------|----------|----------|----------|------|
| **영화** | movie | Movie (BaseItem) | Media (type=video) | VideoModel | metadata_items (type=1) |
| **TV 쇼** | tvshow → seasons → episode | Series → Season → Episode | Media (플랫) | VideoModel (플랫) | parent_id 체인 |
| **컬렉션** | sets | Collections | Playlist | Playlist | Collections |
| **부모-자식** | tvshowlinkepisode | BaseItem.ParentId | Category.parent | - | metadata_items.parent_id |

### 7.3 N:N 관계 처리

| 관계 유형 | Kodi | Jellyfin | MediaCMS | PeerTube |
|----------|------|----------|----------|----------|
| **배우** | actor_link (media_type) | ItemPerson | - | - |
| **장르** | genre_link | ItemGenre | categories (M2M) | - |
| **태그** | tag_link | ItemTag | tags (M2M) | VideoTag (join table) |
| **플레이리스트** | - | - | PlaylistItem (through) | VideoPlaylist |

### 7.4 외부 메타데이터 통합

| 소스 | Kodi | Jellyfin | MediaCMS | PeerTube |
|------|------|----------|----------|----------|
| **IMDb** | uniqueid.type='imdb' | ProviderIds | - | Plugin 지원 |
| **TMDb** | uniqueid.type='tmdb' | ProviderIds | - | Plugin 지원 |
| **TVDB** | uniqueid.type='tvdb' | ProviderIds | - | - |
| **평점** | rating (rating_type) | - | Rating 모델 | likes/dislikes |

### 7.5 재생 추적

| 필드 | Kodi | Jellyfin | MediaCMS | PeerTube |
|------|------|----------|----------|----------|
| **재생 횟수** | files.playCount | UserData.PlayCount | views (비정규화) | views |
| **재생 위치** | bookmark.timeInSeconds | UserData.PlaybackPositionTicks | - | - |
| **마지막 재생** | files.lastPlayed | UserData.LastPlayedDate | - | - |
| **즐겨찾기** | - | UserData.IsFavorite | - | - |

---

## 8. Archive Analyzer 적용 권장사항

### 8.1 스키마 설계 전략

#### Phase 1: 기본 구조 (Kodi 참고)
```sql
-- 파일 테이블 (현재 files 확장)
CREATE TABLE media_files (
    id INTEGER PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    media_type TEXT,  -- 'video', 'audio', 'subtitle'
    size INTEGER,
    duration_seconds INTEGER,

    -- Kodi 방식: 고정 메타데이터 컬럼
    title TEXT,
    description TEXT,
    year INTEGER,

    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- N:N 링크 테이블 (Kodi 패턴)
CREATE TABLE tag_link (
    tag_id INTEGER,
    media_id INTEGER,
    media_type TEXT DEFAULT 'video',
    PRIMARY KEY (tag_id, media_id, media_type)
);

CREATE TABLE player_link (
    player_id INTEGER,
    media_id INTEGER,
    role TEXT,  -- 'featured', 'mentioned'
    PRIMARY KEY (player_id, media_id)
);

CREATE TABLE event_link (
    event_id INTEGER,
    media_id INTEGER,
    PRIMARY KEY (event_id, media_id)
);
```

#### Phase 2: 계층 구조 (Jellyfin 참고)
```sql
-- 카탈로그 계층 (BaseItem 패턴)
CREATE TABLE catalogs (
    id INTEGER PRIMARY KEY,
    catalog_id TEXT UNIQUE,
    parent_id INTEGER,
    depth INTEGER DEFAULT 0,

    name TEXT,
    description TEXT,

    FOREIGN KEY (parent_id) REFERENCES catalogs(id)
);

-- 예: WSOP → WSOP-BR → WSOP-EUROPE (3단 계층)
INSERT INTO catalogs (catalog_id, parent_id, depth, name)
VALUES
    ('wsop', NULL, 0, 'WSOP'),
    ('wsop-br', 1, 1, 'WSOP Big Run'),
    ('wsop-europe', 2, 2, 'WSOP Europe');
```

#### Phase 3: 외부 ID (Kodi uniqueid 패턴)
```sql
CREATE TABLE external_ids (
    id INTEGER PRIMARY KEY,
    media_id INTEGER,
    source TEXT,  -- 'iconik', 'youtube', 'twitch'
    external_id TEXT,
    UNIQUE (media_id, source)
);
```

#### Phase 4: 사용자 추적 (Jellyfin UserData 패턴)
```sql
CREATE TABLE user_playback (
    user_id INTEGER,
    media_id INTEGER,
    playback_position_seconds INTEGER DEFAULT 0,
    play_count INTEGER DEFAULT 0,
    last_played_at TIMESTAMP,
    is_favorite BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (user_id, media_id)
);
```

### 8.2 라이브러리 선택 (MIT/Apache 우선)

| 용도 | 라이브러리 | 라이선스 | 사유 |
|------|-----------|---------|------|
| **메타데이터 추출** | pymediainfo | BSD-2-Clause | MediaInfo 래퍼 (MIT 유사) |
| **썸네일 생성** | ffmpeg-python | Apache-2.0 | FFmpeg 바인딩 |
| **DB ORM** | SQLAlchemy | MIT | Python 표준 ORM |
| **스키마 마이그레이션** | Alembic | MIT | SQLAlchemy 기반 |
| **검색** | MeiliSearch | MIT | 이미 사용 중 |

### 8.3 피해야 할 패턴

| 안티패턴 | 이유 | 대안 |
|---------|------|------|
| **JSON BLOB 메타데이터** | 쿼리 성능 저하, 타입 안전성 없음 | 고정 컬럼 또는 EAV 패턴 |
| **단일 media_metadata 테이블** | 스키마 변경 시 전체 재구축 | 링크 테이블로 분리 |
| **문자열 외래키** | JOIN 성능 저하 | INTEGER PRIMARY KEY |
| **media_type 없는 링크** | 확장성 부족 | Kodi처럼 media_type 추가 |

### 8.4 구현 우선순위

1. **Phase 1 (즉시)**: Kodi 방식 링크 테이블 추가
   - `tag_link`, `player_link`, `event_link`
   - `media_type` 컬럼 포함 (향후 audio/subtitle 확장)

2. **Phase 2 (단기)**: 카탈로그 계층 구조
   - `catalogs.parent_id` self-referencing FK
   - `subcatalog_id` 자동 생성 로직

3. **Phase 3 (중기)**: 외부 메타데이터 통합
   - `external_ids` 테이블
   - iconik CSV → `external_ids.source='iconik'`

4. **Phase 4 (장기)**: 사용자 기능
   - `user_playback` 테이블
   - Admin UI에서 즐겨찾기/재생 위치 추적

---

## 9. 라이선스별 요약

### GPL-2.0 (Jellyfin, Kodi)
- **허용**: 상용 사용, 수정, 배포
- **의무**: 수정 시 소스 공개 (동일 라이선스 유지)
- **제약**: 독점 소프트웨어와 결합 불가
- **권장**: Archive Analyzer는 AGPL이므로 호환 가능

### AGPL-3.0 (MediaCMS, PeerTube)
- **허용**: 상용 사용, 수정, 배포
- **의무**: 네트워크 서비스 제공 시에도 소스 공개 (GPL보다 강력)
- **제약**: SaaS 형태로 제공 시 전체 소스 공개 필요
- **권장**: Archive Analyzer가 이미 AGPL이므로 직접 통합 가능

### LGPL-2.1 (TagLib#)
- **허용**: 상용/독점 소프트웨어와 동적 링킹 가능
- **의무**: LGPL 라이브러리 수정 시만 공개
- **권장**: 메타데이터 추출 라이브러리로 안전하게 사용 가능

### Proprietary (Plex)
- **제약**: 스키마 역공학 가능하나 법적 리스크
- **권장**: 참고만 하고 직접 복사 금지

---

## 10. 참고 자료

### Jellyfin
- [Database System | DeepWiki](https://deepwiki.com/jellyfin/jellyfin/7-database-system)
- [Library database EFCore migration #26](https://github.com/jellyfin/jellyfin-meta/issues/26)
- [SQLite concurrency and WAL](https://jellyfin.org/posts/SQLite-locking/)

### Kodi
- [Databases/MyVideos - Official Kodi Wiki](https://kodi.wiki/view/Databases/MyVideos)
- [Kodi v17.6 DDL Scripts (GitHub Gist)](https://gist.github.com/mrdaliri/0aa1aec8df7cf3fa6f98ff1023da6151)
- [Archive:Database Schema 4.0/a](https://kodi.wiki/view/Archive:Database_Schema_4.0/a)

### MediaCMS
- [GitHub - mediacms-io/mediacms](https://github.com/mediacms-io/mediacms)
- [MediaCMS Documentation](https://github.com/mediacms-io/mediacms/tree/main/docs)

### PeerTube
- [Architecture | PeerTube documentation](https://docs.joinpeertube.org/contribute/architecture)
- [GitHub - Chocobozzz/PeerTube](https://github.com/Chocobozzz/PeerTube)
- [PeerTube Metadata Plugin](https://github.com/biowilli/peertube-plugin-metadata)

### Plex
- [Plex Database Schema (Community)](https://www.databasesample.com/database/plex-database)
- [PLEX database (Google Sites)](https://sites.google.com/site/plexdatabase/schema)
- [Analyzing Plex Data with Power BI](https://ssbipolar.com/2023/01/27/analyzing-plex-media-server-data-using-power-bi/)

### 비교 분석
- [Jellyfin vs Plex | Android Authority](https://www.androidauthority.com/jellyfin-vs-plex-home-server-3360937/)
- [Best Plex alternatives in 2024 | XDA](https://www.xda-developers.com/best-plex-alternatives/)
- [Kodi vs Jellyfin | SmartTVs.org](https://smarttvs.org/kodi-vs-jellyfin/)

---

## 11. 결론

### 권장 스키마 전략

**Archive Analyzer 최적 조합**:
1. **Kodi 링크 테이블 패턴** → N:N 관계 (tag, player, event)
2. **Jellyfin 계층 구조** → catalogs.parent_id
3. **MediaCMS 상태 관리** → state, encoding_status
4. **자체 설계** → pokervod.db 통합 (OTT 특화)

**라이선스 호환성**:
- Archive Analyzer는 AGPL이므로 GPL/AGPL 솔루션 참고 가능
- MIT/Apache 라이선스 전용 미디어 DB는 없으므로 독자 설계 필요
- TagLib# (LGPL)은 메타데이터 추출만 사용

**다음 단계**:
1. `docs/DATABASE_SCHEMA.md`에 Kodi 링크 테이블 추가
2. `catalogs` 테이블 재설계 (parent_id 추가)
3. SQLAlchemy 마이그레이션 스크립트 작성
