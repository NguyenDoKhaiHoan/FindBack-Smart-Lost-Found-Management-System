import { PageHeading } from '../../components/ui/shared'

const photos = [
  {
    title: 'Máy tính xách tay',
    author: 'Ghost Presenter',
    license: 'CC0 1.0',
    sourceUrl: 'https://commons.wikimedia.org/wiki/File:Monochrome_MacBook_in_Library.jpg',
    licenseUrl: 'https://creativecommons.org/publicdomain/zero/1.0/',
  },
  {
    title: 'Ba lô',
    author: 'Joe from Backpack and Gear',
    license: 'Phạm vi công cộng',
    sourceUrl: 'https://commons.wikimedia.org/wiki/File:Backpack.jpg',
    licenseUrl: 'https://commons.wikimedia.org/wiki/File:Backpack.jpg#Licensing',
  },
  {
    title: 'Ví da',
    author: 'Eugene Pik',
    license: 'CC BY-SA 4.0',
    sourceUrl:
      'https://commons.wikimedia.org/wiki/File:Leather_bi-fold_wallet_by_Eugene_Pik_(2021)_04.jpg',
    licenseUrl: 'https://creativecommons.org/licenses/by-sa/4.0/',
  },
  {
    title: 'Máy ảnh',
    author: 'Vera de Kok',
    license: 'CC0 1.0',
    sourceUrl: 'https://commons.wikimedia.org/wiki/File:Canon_EOS_250D.jpg',
    licenseUrl: 'https://creativecommons.org/publicdomain/zero/1.0/',
  },
  {
    title: 'Điện thoại',
    author: 'Acabashi',
    license: 'CC BY-SA 4.0',
    sourceUrl:
      'https://commons.wikimedia.org/wiki/File:Blackview_A60_Smartphone_Android_mobile_phone_and_folio_case.jpg',
    licenseUrl: 'https://creativecommons.org/licenses/by-sa/4.0/',
  },
  {
    title: 'Đồng hồ đeo tay',
    author: 'Auckland War Memorial Museum Tāmaki Paenga Hira',
    license: 'CC BY 4.0',
    sourceUrl: 'https://commons.wikimedia.org/wiki/File:Watch,_wrist_(AM_2014.7.70-10).jpg',
    licenseUrl: 'https://creativecommons.org/licenses/by/4.0/',
  },
]

export function PhotoCreditsPage() {
  return (
    <div className="container page-container narrow">
      <PageHeading
        title="Nguồn ảnh"
        description="Tác giả và giấy phép của các ảnh minh họa từ Wikimedia Commons."
      />
      <div className="live-stack">
        {photos.map((photo) => (
          <article className="panel" key={photo.sourceUrl}>
            <h2>{photo.title}</h2>
            <p>
              {photo.author} · {photo.license}. Ảnh được thu nhỏ.
            </p>
            <div className="live-actions">
              <a className="text-link" href={photo.sourceUrl} target="_blank" rel="noreferrer">
                Ảnh gốc
              </a>
              <a className="text-link" href={photo.licenseUrl} target="_blank" rel="noreferrer">
                Giấy phép
              </a>
            </div>
          </article>
        ))}
      </div>
    </div>
  )
}
